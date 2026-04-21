import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import redis

from .config import Config


ENGINE_REDIS = 1
ENGINE_KVROCKS = 2
ENGINE_PIKA = 3


class RedisSentinel:
    def __init__(self, sentinel_name):
        """初始化Redis Sentinel客户端"""
        self.sentinel_name = sentinel_name
        self.sentinel_config = Config.get_sentinel_config(sentinel_name)
        if not self.sentinel_config:
            raise ValueError(f"Sentinel配置 '{sentinel_name}' 不存在")

        self.default_password = self.sentinel_config.get('default_password', '')
        self.master_groups = self.sentinel_config.get('master_groups', {})
        self.sentinel_hosts = self.sentinel_config.get('sentinel_hosts', [])

        metrics_config = Config.get_metrics_config()
        self.thread_pool_size = metrics_config.get('thread_pool_size', 10)
        self.connect_timeout = metrics_config.get('connect_timeout', 3)
        self.read_timeout = metrics_config.get('read_timeout', 5)
        self.discovery_ttl = metrics_config.get('discovery_ttl', 30)

        self.sentinel_clients = []
        self.sentinel_status = []
        self.all_master_names = []
        self._last_discovery_at = 0

        self.last_scrape_success = False
        self.last_scrape_duration = 0
        self.last_scrape_error = ""

        self._create_sentinel_clients()
        self.refresh_master_names(force=True)

    def _create_sentinel_clients(self):
        """创建Sentinel客户端连接"""
        clients = []
        status = []
        for sentinel in self.sentinel_hosts:
            host = sentinel['host']
            port = sentinel['port']
            client = redis.Redis(
                host=host,
                port=port,
                socket_timeout=self.connect_timeout,
                socket_connect_timeout=self.connect_timeout,
                decode_responses=True,
            )
            try:
                client.ping()
                clients.append(client)
                status.append({'host': host, 'port': port, 'up': 1, 'error': ''})
            except redis.RedisError as exc:
                status.append({'host': host, 'port': port, 'up': 0, 'error': str(exc)})
                logging.warning("无法连接到Sentinel %s:%s - %s", host, port, exc)

        if not clients:
            logging.error("无法连接到任何Sentinel服务器")

        self.sentinel_clients = clients
        self.sentinel_status = status

    def refresh_master_names(self, force=False):
        """按TTL刷新master名称列表。"""
        now = time.time()
        if not force and self.all_master_names and now - self._last_discovery_at < self.discovery_ttl:
            return self.all_master_names

        if not self.sentinel_clients:
            self._create_sentinel_clients()

        discovered = []
        for client in self.sentinel_clients:
            try:
                masters_info = client.sentinel_masters()
                if masters_info:
                    discovered = sorted(masters_info.keys())
                    break
            except redis.RedisError as exc:
                logging.warning("从Sentinel获取master列表失败: %s", exc)

        if discovered:
            self.all_master_names = discovered
            self._last_discovery_at = now
            logging.info("从Sentinel发现%d个master: %s", len(discovered), ", ".join(discovered))
        elif not self.all_master_names:
            logging.warning("无法从任何Sentinel获取master列表")

        return self.all_master_names

    def get_master_by_name(self, master_name):
        """通过master_name获取主节点信息"""
        self.refresh_master_names()
        for client in self.sentinel_clients:
            try:
                master_info = client.sentinel_master(master_name)
                if master_info:
                    return master_info
            except redis.RedisError as exc:
                logging.warning("从Sentinel获取主节点信息失败: %s, master_name: %s", exc, master_name)

        return None

    def get_slaves_by_name(self, master_name):
        """通过master_name获取从节点信息"""
        self.refresh_master_names()
        for client in self.sentinel_clients:
            try:
                slaves_info = client.sentinel_slaves(master_name)
                if slaves_info:
                    connected_slaves = []
                    for slave in slaves_info:
                        is_connected = not slave.get('is_disconnected', True)
                        flags = str(slave.get('flags', '')).lower()
                        is_not_down = 'down' not in flags
                        if is_connected and is_not_down:
                            connected_slaves.append(slave)

                    return connected_slaves
            except redis.RedisError as exc:
                logging.warning("从Sentinel获取从节点信息失败: %s, master_name: %s", exc, master_name)

        return []

    def get_all_masters(self):
        """获取所有主节点信息"""
        return {
            master_name: master_info
            for master_name in self.refresh_master_names()
            if (master_info := self.get_master_by_name(master_name))
        }

    def get_all_slaves(self):
        """获取所有从节点信息"""
        slaves_info = {}
        for master_name in self.refresh_master_names():
            slaves = self.get_slaves_by_name(master_name)
            if slaves:
                slaves_info[master_name] = slaves
        return slaves_info

    def get_redis_password(self, master_name):
        """获取特定主节点的密码"""
        master_config = self.master_groups.get(master_name, {})
        if isinstance(master_config, dict) and 'password' in master_config:
            return master_config['password']

        return self.default_password

    def get_redis_client(self, host, port, master_name):
        """获取Redis客户端连接"""
        return redis.Redis(
            host=host,
            port=port,
            password=self.get_redis_password(master_name),
            socket_timeout=self.read_timeout,
            socket_connect_timeout=self.connect_timeout,
            decode_responses=True,
        )

    @staticmethod
    def detect_engine(info):
        if 'disk_capacity' in info:
            return ENGINE_KVROCKS
        if 'pika_version' in info or 'pika_build_id' in info:
            return ENGINE_PIKA
        return ENGINE_REDIS

    @staticmethod
    def calculate_total_keys(info):
        if 'total_keys' in info:
            try:
                return int(info['total_keys'])
            except (TypeError, ValueError):
                return 0

        total_keys = 0
        for key, value in info.items():
            if key.startswith('db') and isinstance(value, dict) and 'keys' in value:
                try:
                    total_keys += int(value['keys'])
                except (ValueError, TypeError):
                    logging.warning("处理键数量时出错，无效值: %s", value['keys'])
        return total_keys

    @staticmethod
    def _failed_node(host, port, master_name, node_role, error):
        return {
            'up': 0,
            'host': host,
            'port': port,
            'master_name': master_name,
            'node_role': node_role,
            'type': ENGINE_REDIS,
            'error': error,
        }

    def _read_kvrocks_total_keys(self, client, info):
        try:
            keyspace_info = client.execute_command('info', 'keyspace')
        except redis.RedisError as exc:
            logging.debug("获取KVRocks键总数失败: %s", exc)
            return

        if isinstance(keyspace_info, dict) and 'total_keys' in keyspace_info:
            info['total_keys'] = keyspace_info['total_keys']
            return

        if isinstance(keyspace_info, str) and 'total_keys' in keyspace_info:
            for line in keyspace_info.splitlines():
                if line.startswith('total_keys:'):
                    try:
                        info['total_keys'] = int(line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                    return

    def collect_redis_info(self, host, port, master_name, node_role):
        """收集Redis节点的信息"""
        client = self.get_redis_client(host, port, master_name)
        try:
            client.ping()
            info = client.info()
            command_stats = client.info('commandstats')
            if command_stats:
                info['commandstats'] = command_stats

            node_type = self.detect_engine(info)
            info.update({
                'up': 1,
                'master_name': master_name,
                'node_role': node_role,
                'host': host,
                'port': port,
                'type': node_type,
                'is_kvrocks': node_type == ENGINE_KVROCKS,
            })

            if node_type == ENGINE_KVROCKS:
                self._read_kvrocks_total_keys(client, info)

            total_keys = self.calculate_total_keys(info)
            if total_keys:
                info['total_keys'] = total_keys

            logging.debug(
                "完成Redis节点采集 host=%s port=%s master=%s role=%s engine=%s",
                host,
                port,
                master_name,
                node_role,
                node_type,
            )
            return info
        except redis.RedisError as exc:
            logging.warning("从Redis %s:%s 获取信息失败, master_name=%s - %s", host, port, master_name, exc)
            return self._failed_node(host, port, master_name, node_role, str(exc))
        finally:
            client.close()

    def _discover_nodes(self):
        all_nodes = []

        for master_name, master_info in self.get_all_masters().items():
            host = master_info.get('ip')
            port = master_info.get('port')
            if host and port:
                all_nodes.append({
                    'host': host,
                    'port': port,
                    'master_name': master_name,
                    'node_role': 'master',
                })

        for master_name, slaves in self.get_all_slaves().items():
            for slave in slaves:
                host = slave.get('ip')
                port = slave.get('port')
                if host and port:
                    all_nodes.append({
                        'host': host,
                        'port': port,
                        'master_name': master_name,
                        'node_role': 'slave',
                    })

        return all_nodes

    def collect_all_redis_info(self):
        """并行收集所有Redis节点的信息"""
        start_time = time.time()
        self.last_scrape_success = False
        self.last_scrape_error = ""
        results = {}

        all_nodes = self._discover_nodes()
        if not all_nodes:
            self.last_scrape_duration = time.time() - start_time
            self.last_scrape_error = "no redis nodes discovered"
            return results

        with ThreadPoolExecutor(max_workers=self.thread_pool_size) as executor:
            future_to_node = {
                executor.submit(
                    self.collect_redis_info,
                    node['host'],
                    node['port'],
                    node['master_name'],
                    node['node_role'],
                ): node for node in all_nodes
            }

            for future in as_completed(future_to_node):
                node = future_to_node[future]
                node_key = f"{node['host']}:{node['port']}"
                try:
                    results[node_key] = future.result()
                except Exception as exc:
                    logging.exception("收集节点 %s 信息失败", node_key)
                    results[node_key] = self._failed_node(
                        node['host'],
                        node['port'],
                        node['master_name'],
                        node['node_role'],
                        str(exc),
                    )

        self.last_scrape_duration = time.time() - start_time
        self.last_scrape_success = bool(results) and all(info.get('up') == 1 for info in results.values())
        if not self.last_scrape_success:
            self.last_scrape_error = "one or more redis nodes failed"

        return results
