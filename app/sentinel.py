import json

import redis
import logging
import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config import Config

class RedisSentinel:
    def __init__(self, sentinel_name):
        """初始化Redis Sentinel客户端"""
        self.sentinel_name = sentinel_name
        self.sentinel_config = Config.get_sentinel_config(sentinel_name)
        if not self.sentinel_config:
            raise ValueError(f"Sentinel配置 '{sentinel_name}' 不存在")

        # 使用该sentinel组的默认密码
        self.default_password = self.sentinel_config.get('default_password', '')
        self.master_groups = self.sentinel_config.get('master_groups', {})

        # 兼容新旧配置结构
        if 'sentinel_hosts' in self.sentinel_config:
            self.sentinel_hosts = self.sentinel_config.get('sentinel_hosts', [])
        else:
            self.sentinel_hosts = self.sentinel_config.get('sentinel_hosts', [])

        # 获取指标收集配置
        metrics_config = Config.get_metrics_config()
        self.thread_pool_size = metrics_config.get('thread_pool_size', 10)
        self.connect_timeout = metrics_config.get('connect_timeout', 3)
        self.read_timeout = metrics_config.get('read_timeout', 5)

        self.sentinel_clients = self._create_sentinel_clients()

        # 从Sentinel API获取所有master_name
        self.all_master_names = self._discover_master_names()

    def _create_sentinel_clients(self):
        """创建Sentinel客户端连接"""
        clients = []
        for sentinel in self.sentinel_hosts:
            try:
                host = sentinel['host']
                port = sentinel['port']
                client = redis.Redis(
                    host=host,
                    port=port,
                    socket_timeout=self.connect_timeout,
                    socket_connect_timeout=self.connect_timeout
                )
                # 测试连接
                client.ping()
                clients.append(client)
            except Exception as e:
                logging.error(f"无法连接到Sentinel {sentinel['host']}:{sentinel['port']} - {str(e)}")

        if not clients:
            logging.error(f"无法连接到任何Sentinel服务器")

        return clients

    def _discover_master_names(self):
        """从Sentinel API获取所有受监控的master名称"""
        if not self.sentinel_clients:
            logging.error("没有有效的Sentinel连接，无法发现master_name")
            return []

        # 尝试每个sentinel客户端直到成功获取master名称
        for client in self.sentinel_clients:
            try:
                # 使用SENTINEL masters命令获取所有master信息
                masters_info = client.sentinel_masters()
                if masters_info:
                    master_names = list(masters_info.keys())
                    logging.info(f"从Sentinel发现了{len(master_names)}个master: {', '.join(master_names)}")
                    return master_names
            except Exception as e:
                logging.error(f"从Sentinel获取master列表失败: {str(e)}")
                continue

        logging.warning("无法从任何Sentinel获取master列表")
        return []

    def get_master_by_name(self, master_name):
        """通过master_name获取主节点信息"""
        if not self.sentinel_clients:
            return None

        # 尝试每个sentinel客户端直到找到有效信息
        for client in self.sentinel_clients:
            try:
                master_info = client.sentinel_master(master_name)
                if master_info:
                    return master_info
            except Exception as e:
                logging.error(f"从Sentinel获取主节点信息失败: {str(e)}, master_name: {master_name}")
                continue

        return None

    def get_slaves_by_name(self, master_name):
        """通过master_name获取从节点信息"""
        if not self.sentinel_clients:
            return []

        # 尝试每个sentinel客户端直到找到有效信息
        for client in self.sentinel_clients:
            try:
                slaves_info = client.sentinel_slaves(master_name)
                if slaves_info:
                    # 过滤掉已断开连接的从节点（检查is_disconnected和flags）
                    connected_slaves = []
                    for slave in slaves_info:
                        # 检查连接状态
                        is_connected = slave.get('is_disconnected', True) == False
                        # 检查flags是否包含down
                        flags = slave.get('flags', '').lower()
                        is_not_down = 'down' not in flags
                        
                        # 只保留既连接正常又不是down状态的节点
                        if is_connected and is_not_down:
                            connected_slaves.append(slave)
                    
                    return connected_slaves
            except Exception as e:
                logging.error(f"从Sentinel获取从节点信息失败: {str(e)}, master_name: {master_name}")
                continue

        return []

    def get_all_masters(self):
        """获取所有主节点信息"""
        masters_info = {}

        # 使用从Sentinel自动发现的master_name列表
        for master_name in self.all_master_names:
            master_info = self.get_master_by_name(master_name)
            if master_info:
                masters_info[master_name] = master_info

        return masters_info

    def get_all_slaves(self):
        """获取所有从节点信息"""
        slaves_info = {}

        # 使用从Sentinel自动发现的master_name列表
        for master_name in self.all_master_names:
            slaves = self.get_slaves_by_name(master_name)
            if slaves:
                slaves_info[master_name] = slaves

        return slaves_info

    def get_redis_password(self, master_name):
        """获取特定主节点的密码"""
        # 如果在master_groups中指定了密码，使用指定密码
        if (master_name in self.master_groups and
            isinstance(self.master_groups[master_name], dict) and
            'password' in self.master_groups[master_name]):
            return self.master_groups[master_name]['password']

        # 否则使用sentinel组的默认密码
        return self.default_password

    def get_redis_client(self, host, port, master_name):
        """获取Redis客户端连接"""
        password = self.get_redis_password(master_name)

        try:
            client = redis.Redis(
                host=host,
                port=port,
                password=password,
                socket_timeout=self.read_timeout,
                socket_connect_timeout=self.connect_timeout,
                decode_responses=True
            )
            # 测试连接
            client.ping()
            return client
        except Exception as e:
            logging.error(f"无法连接到Redis {host}:{port}, master_name: {master_name} - {str(e)}")
            return None

    def collect_redis_info(self, host, port, master_name, node_role):
        """收集Redis节点的信息"""
        client = self.get_redis_client(host, port, master_name)
        if not client:
            return None

        try:
            info = client.info()
            info['master_name'] = master_name
            info['node_role'] = node_role
            info['host'] = host
            info['port'] = port

            # 获取命令统计信息
            command_stats = client.info('commandstats')
            if command_stats:
                info['commandstats'] = command_stats

            # 获取数据库键信息
            keyspace = client.info('keyspace')
            if keyspace:
                logging.debug(f"节点 {host}:{port} 的键空间信息: {pprint.pformat(keyspace)}")

            # 判断是否是KVRocks节点 - 使用disk_capacity字段判断
            is_kvrocks = 'disk_capacity' in info
            info['is_kvrocks'] = is_kvrocks
            
            # 判断节点类型：1=Redis, 2=KVRocks, 3=Pika
            node_type = 1  # 默认为Redis
            
            if is_kvrocks:
                node_type = 2  # KVRocks
            
            # 未来可以添加Pika判断逻辑，例如检查Pika特有的字段
            # 示例：判断Pika的逻辑(根据实际的Pika节点特性调整)
            # is_pika = False
            # if 'pika_version' in info or 'pika_build_id' in info:
            #     is_pika = True
            #     node_type = 3
            #     logging.info(f"检测到Pika节点 {host}:{port}, 版本: {info.get('pika_version', '未知')}")
            
            # 设置节点类型
            info['type'] = node_type

            # 对于KVRocks，尝试获取total_keys
            if is_kvrocks:
                logging.info(f"检测到KVRocks节点 {host}:{port}, 磁盘容量: {info.get('disk_capacity', '未知')}")
                try:
                    # 有些KVRocks版本可能提供特殊命令获取键总数
                    total_keys_info = client.execute_command('info', 'keyspace')
                    if isinstance(total_keys_info, dict) and 'total_keys' in total_keys_info:
                        info['total_keys'] = total_keys_info['total_keys']
                    elif isinstance(total_keys_info, str) and 'total_keys' in total_keys_info:
                        # 解析字符串格式的响应
                        for line in total_keys_info.splitlines():
                            if line.startswith('total_keys:'):
                                key_count = line.split(':')[1].strip()
                                try:
                                    info['total_keys'] = int(key_count)
                                    break
                                except ValueError:
                                    pass

                    if 'total_keys' in info:
                        logging.info(f"KVRocks节点 {host}:{port} 键总数: {info['total_keys']}")
                except Exception as e:
                    logging.warning(f"获取KVRocks节点 {host}:{port} 键总数失败: {str(e)}")

            # 计算总键数（适用于普通Redis节点）
            if 'total_keys' not in info:
                total_keys = 0
                for key, value in info.items():
                    if key.startswith('db') and isinstance(value, dict) and 'keys' in value:
                        try:
                            total_keys += int(value['keys'])
                        except (ValueError, TypeError):
                            logging.warning(f"处理键数量时出错，无效值: {value['keys']}")

                # 如果在db*中找到了键，添加到总键数
                if total_keys > 0:
                    info['total_keys'] = total_keys
                    logging.info(f"Redis节点 {host}:{port} 从db*计算的总键数: {total_keys}")
            logging.info(f"{master_name} info is {json.dumps(info)}")
            return info
        except Exception as e:
            logging.error(f"从Redis {host}:{port} 获取信息失败: {str(e)}")
            return None
        finally:
            client.close()

    def collect_all_redis_info(self):
        """并行收集所有Redis节点的信息"""
        all_nodes = []
        results = {}

        # 获取所有主节点
        masters = self.get_all_masters()
        for master_name, master_info in masters.items():
            # 提取IP和端口
            host = master_info.get('ip')
            port = master_info.get('port')
            if host and port:
                all_nodes.append({
                    'host': host,
                    'port': port,
                    'master_name': master_name,
                    'node_role': 'master'
                })

        # 获取所有从节点
        slaves_by_master = self.get_all_slaves()
        for master_name, slaves in slaves_by_master.items():
            for slave in slaves:
                host = slave.get('ip')
                port = slave.get('port')
                if host and port:
                    all_nodes.append({
                        'host': host,
                        'port': port,
                        'master_name': master_name,
                        'node_role': 'slave'
                    })

        # 并行收集节点信息
        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            # 提交所有任务
            future_to_node = {
                executor.submit(
                    self.collect_redis_info,
                    node['host'],
                    node['port'],
                    node['master_name'],
                    node['node_role']
                ): node for node in all_nodes
            }

            # 收集结果
            for future in as_completed(future_to_node):
                node = future_to_node[future]
                try:
                    info = future.result()
                    if info:
                        node_key = f"{node['host']}:{node['port']}"
                        results[node_key] = info
                except Exception as e:
                    logging.error(f"收集节点 {node['host']}:{node['port']} 信息失败: {str(e)}")

        return results 