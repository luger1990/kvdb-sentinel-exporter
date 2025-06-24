from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST, Info, CollectorRegistry
import logging
import re


class RedisMetricsCollector:
    """Redis指标收集器"""

    def __init__(self):
        # 创建独立的注册表，避免使用全局默认注册表
        self.registry = CollectorRegistry()

        # 基本指标
        self.up = Gauge('kvdb_up', 'Redis实例是否在线', ['db_instance', 'group_name', 'role', 'sentinel_name'],
                        registry=self.registry)

        # 节点角色指标，1表示主库，0表示从库
        self.node_role = Gauge('kvdb_role', 'Redis节点角色(1=主库, 0=从库)',
                               ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)

        # 按照用户要求定义的指标
        self.uptime_in_seconds = Gauge('kvdb_uptime_in_seconds', 'Redis实例运行时间（秒）',
                                       ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.connected_clients = Gauge('kvdb_connected_clients', 'Redis连接的客户端数量',
                                       ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.max_clients = Gauge('kvdb_max_clients', 'Redis最大客户端连接数',
                                 ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.blocked_clients = Gauge('kvdb_blocked_clients', 'Redis阻塞的客户端数量',
                                     ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.memory_used_bytes = Gauge('kvdb_memory_used_bytes', 'Redis已使用内存字节数',
                                       ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.memory_max_bytes = Gauge('kvdb_memory_max_bytes', 'Redis最大可用内存字节数',
                                      ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.commands_processed_total = Gauge('kvdb_commands_processed_total', 'Redis处理的命令总数',
                                              ['db_instance', 'group_name', 'role', 'sentinel_name'],
                                              registry=self.registry)
        self.net_input_bytes_total = Gauge('kvdb_net_input_bytes_total', 'Redis接收的总字节数',
                                           ['db_instance', 'group_name', 'role', 'sentinel_name'],
                                           registry=self.registry)
        self.net_output_bytes_total = Gauge('kvdb_net_output_bytes_total', 'Redis发送的总字节数',
                                            ['db_instance', 'group_name', 'role', 'sentinel_name'],
                                            registry=self.registry)
        self.net_input_kbps = Gauge('kvdb_net_input_kbps', '进入Redis的网络流量(KB/s)',
                                    ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.net_output_kbps = Gauge('kvdb_net_output_kbps', '从Redis流出的网络流量(KB/s)',
                                     ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.db_keys = Gauge('kvdb_db_keys', 'Redis数据库中的键数量',
                             ['db_instance', 'group_name', 'role', 'db', 'sentinel_name'], registry=self.registry)
        self.db_keys_expiring = Gauge('kvdb_db_keys_expiring', 'Redis数据库中设置了过期时间的键数量',
                                      ['db_instance', 'group_name', 'role', 'db', 'sentinel_name'],
                                      registry=self.registry)
        self.evicted_keys_total = Gauge('kvdb_evicted_keys_total', 'Redis因内存限制被驱逐的键数量',
                                        ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.commands_total = Gauge('kvdb_commands_total', 'Redis各命令的执行次数',
                                    ['db_instance', 'group_name', 'role', 'command', 'sentinel_name'],
                                    registry=self.registry)
        self.slowlog_length = Gauge('kvdb_slowlog_length', 'Redis慢日志的长度',
                                    ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.connected_slaves = Gauge('kvdb_connected_slaves', 'Redis连接的从节点数量',
                                      ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.master_last_io_seconds_ago = Gauge('kvdb_master_last_io_seconds_ago',
                                                '主节点最后一次与从节点通信的时间（秒）',
                                                ['db_instance', 'group_name', 'role', 'sentinel_name'],
                                                registry=self.registry)
        self.master_repl_offset = Gauge('kvdb_master_repl_offset', '主节点复制偏移量',
                                        ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.instantaneous_ops_per_sec = Gauge('kvdb_instantaneous_ops_per_sec', '当前每秒执行的命令数',
                                               ['db_instance', 'group_name', 'role', 'sentinel_name'],
                                               registry=self.registry)
        self.version = Gauge('kvdb_version', 'Redis版本号（去掉小数点）',
                             ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.port = Gauge('kvdb_port', 'Redis监听端口',
                          ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)

        # 新增引擎类型指标 - 1表示Redis，2表示KVRocks
        self.engine_type = Gauge('kvdb_engine_type', '引擎类型(1=Redis, 2=KVRocks)',
                                 ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)

        # 硬盘存储类型的引擎存储数据所占硬盘字节数
        self.db_used_bytes = Gauge('kvdb_db_used_bytes', '硬盘存储类型的引擎存储数据所占硬盘字节数',
                                   ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.disk_used_bytes = Gauge('kvdb_disk_used_bytes', '当前硬盘总使用字节数',
                                     ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)
        self.disk_max_bytes = Gauge('kvdb_disk_max_bytes', '当前硬盘总字节数',
                                    ['db_instance', 'group_name', 'role', 'sentinel_name'], registry=self.registry)

    def collect_metrics(self, redis_info_dict, sentinel_name):
        """从Redis信息收集指标"""

        # 收集每个Redis实例的指标
        for instance, info in redis_info_dict.items():
            master_name = info.get('master_name', 'unknown')
            role = info.get('node_role', 'unknown')

            # 使用新的type字段判断引擎类型
            node_type = info.get('type', 1)  # 默认为Redis(1)
            is_kvrocks = node_type == 2  # 兼容现有代码

            # 设置实例在线状态
            self.up.labels(db_instance=instance, group_name=master_name, role=role, sentinel_name=sentinel_name).set(1)

            # 设置节点角色
            is_master = 1 if role == 'master' else 0
            self.node_role.labels(db_instance=instance, group_name=master_name, role=role,
                                  sentinel_name=sentinel_name).set(is_master)

            # 设置引擎类型 (使用新的type字段)
            self.engine_type.labels(db_instance=instance, group_name=master_name, role=role,
                                    sentinel_name=sentinel_name).set(node_type)

            # 实例运行时间
            uptime = info.get('uptime_in_seconds', 0)
            self.uptime_in_seconds.labels(db_instance=instance, group_name=master_name, role=role,
                                          sentinel_name=sentinel_name).set(uptime)

            # 客户端连接
            if 'connected_clients' in info:
                self.connected_clients.labels(db_instance=instance, group_name=master_name, role=role,
                                              sentinel_name=sentinel_name).set(
                    info['connected_clients'])

            # 最大客户端连接
            if 'maxclients' in info:
                self.max_clients.labels(db_instance=instance, group_name=master_name, role=role,
                                        sentinel_name=sentinel_name).set(info['maxclients'])

            # 阻塞客户端
            if 'blocked_clients' in info:
                self.blocked_clients.labels(db_instance=instance, group_name=master_name, role=role,
                                            sentinel_name=sentinel_name).set(
                    info['blocked_clients'])

            # 内存使用情况
            if 'used_memory_rss' in info:
                self.memory_used_bytes.labels(db_instance=instance, group_name=master_name, role=role,
                                              sentinel_name=sentinel_name).set(
                    info['used_memory_rss'])

            # 最大内存
            max_memory = 0
            if not is_kvrocks:
                max_memory = info.get('maxmemory', 0)
            self.memory_max_bytes.labels(db_instance=instance, group_name=master_name, role=role,
                                         sentinel_name=sentinel_name).set(max_memory)

            # 处理命令总数
            if 'total_commands_processed' in info:
                self.commands_processed_total.labels(db_instance=instance, group_name=master_name, role=role,
                                                     sentinel_name=sentinel_name).set(
                    info['total_commands_processed'])

            # 网络流量
            if 'total_net_input_bytes' in info:
                self.net_input_bytes_total.labels(db_instance=instance, group_name=master_name, role=role,
                                                  sentinel_name=sentinel_name).set(
                    info['total_net_input_bytes'])

            if 'total_net_output_bytes' in info:
                self.net_output_bytes_total.labels(db_instance=instance, group_name=master_name, role=role,
                                                   sentinel_name=sentinel_name).set(
                    info['total_net_output_bytes'])

            # 网络流量速率
            if 'instantaneous_input_kbps' in info:
                self.net_input_kbps.labels(db_instance=instance, group_name=master_name, role=role,
                                           sentinel_name=sentinel_name).set(
                    info['instantaneous_input_kbps'])

            if 'instantaneous_output_kbps' in info:
                self.net_output_kbps.labels(db_instance=instance, group_name=master_name, role=role,
                                            sentinel_name=sentinel_name).set(
                    info['instantaneous_output_kbps'])

            # 键空间统计
            for key, value in info.items():
                if key.startswith('db'):
                    db_name = key
                    if isinstance(value, dict):
                        if 'keys' in value:
                            self.db_keys.labels(db_instance=instance, group_name=master_name, role=role,
                                                sentinel_name=sentinel_name, db=db_name).set(
                                value['keys'])
                        if 'expires' in value:
                            self.db_keys_expiring.labels(db_instance=instance, group_name=master_name, role=role,
                                                         sentinel_name=sentinel_name,
                                                         db=db_name).set(value['expires'])

            # 驱逐的键数量
            if 'evicted_keys' in info:
                self.evicted_keys_total.labels(db_instance=instance, group_name=master_name, role=role,
                                               sentinel_name=sentinel_name).set(
                    info['evicted_keys'])

            # 命令统计
            if 'commandstats' in info:
                for cmd, stats in info['commandstats'].items():
                    cmd_name = cmd.replace('cmdstat_', '')
                    if 'calls' in stats:
                        self.commands_total.labels(
                            db_instance=instance,
                            group_name=master_name,
                            role=role,
                            sentinel_name=sentinel_name,
                            command=cmd_name
                        ).set(stats['calls'])

            # 慢日志长度
            try:
                # 如果有slowlog_len字段则直接使用
                if 'slowlog_len' in info:
                    self.slowlog_length.labels(db_instance=instance, group_name=master_name, role=role,
                                               sentinel_name=sentinel_name).set(
                        info['slowlog_len'])
                # 否则可能需要后续添加获取慢日志长度的代码
            except Exception as e:
                logging.warning(f"无法获取慢日志长度: {str(e)}")

            # 连接的从节点
            if 'connected_slaves' in info:
                self.connected_slaves.labels(db_instance=instance, group_name=master_name, role=role,
                                             sentinel_name=sentinel_name).set(
                    info['connected_slaves'])

            # 主节点与从节点最后通信时间
            if 'master_last_io_seconds_ago' in info:
                self.master_last_io_seconds_ago.labels(db_instance=instance, group_name=master_name, role=role,
                                                       sentinel_name=sentinel_name).set(
                    info['master_last_io_seconds_ago'])

            # 复制偏移量
            if 'master_repl_offset' in info:
                self.master_repl_offset.labels(db_instance=instance, group_name=master_name, role=role,
                                               sentinel_name=sentinel_name).set(
                    info['master_repl_offset'])

            # 每秒执行的操作数
            if 'instantaneous_ops_per_sec' in info:
                self.instantaneous_ops_per_sec.labels(db_instance=instance, group_name=master_name, role=role,
                                                      sentinel_name=sentinel_name).set(
                    info['instantaneous_ops_per_sec'])

            if is_kvrocks:
                if 'used_db_size' in info:
                    self.db_used_bytes.labels(db_instance=instance, group_name=master_name, role=role,
                                                  sentinel_name=sentinel_name).set(
                        info['used_db_size'])
                if 'used_disk_size' in info:
                    self.disk_used_bytes.labels(db_instance=instance, group_name=master_name, role=role,
                                                sentinel_name=sentinel_name).set(
                        info['used_disk_size'])
                if 'disk_capacity' in info:
                    self.disk_max_bytes.labels(db_instance=instance, group_name=master_name, role=role,
                                               sentinel_name=sentinel_name).set(
                        info['disk_capacity'])

            # 版本信息处理
            version_value = 0
            if is_kvrocks and 'version' in info:
                version_str = info['version']
                # 提取数字部分
                version_digits = re.sub(r'[^\d]', '', version_str)
                if version_digits:
                    version_value = int(version_digits)
            elif not is_kvrocks and 'redis_version' in info:
                version_str = info['redis_version']
                # 提取数字部分
                version_digits = re.sub(r'[^\d]', '', version_str)
                if version_digits:
                    version_value = int(version_digits)

            self.version.labels(db_instance=instance, group_name=master_name, role=role,
                                sentinel_name=sentinel_name).set(version_value)

            # 端口信息
            if 'tcp_port' in info:
                self.port.labels(db_instance=instance, group_name=master_name, role=role,
                                 sentinel_name=sentinel_name).set(info['tcp_port'])

    def get_metrics(self):
        """获取指标数据"""
        return generate_latest(self.registry)

    def get_content_type(self):
        """获取内容类型"""
        return CONTENT_TYPE_LATEST
