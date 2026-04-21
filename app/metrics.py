from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest


class RedisMetricsCollector:
    """Redis指标收集器"""

    BASE_LABELS = ['db_instance', 'db_instance_ip', 'group_name', 'role', 'sentinel_name']

    def __init__(self):
        self.registry = CollectorRegistry()

        self.scrape_success = Gauge(
            'kvdb_scrape_success',
            '本次采集是否完全成功',
            ['sentinel_name'],
            registry=self.registry,
        )
        self.scrape_duration_seconds = Gauge(
            'kvdb_scrape_duration_seconds',
            '本次采集耗时',
            ['sentinel_name'],
            registry=self.registry,
        )
        self.sentinel_up = Gauge(
            'kvdb_sentinel_up',
            'Sentinel实例是否在线',
            ['sentinel_name', 'sentinel_host', 'sentinel_port'],
            registry=self.registry,
        )

        self.up = Gauge('kvdb_up', 'Redis实例是否在线', self.BASE_LABELS, registry=self.registry)
        self.node_role = Gauge('kvdb_role', 'Redis节点角色(1=主库, 0=从库)', self.BASE_LABELS, registry=self.registry)
        self.uptime_in_seconds = Gauge('kvdb_uptime_in_seconds', 'Redis实例运行时间（秒）', self.BASE_LABELS, registry=self.registry)
        self.connected_clients = Gauge('kvdb_connected_clients', 'Redis连接的客户端数量', self.BASE_LABELS, registry=self.registry)
        self.max_clients = Gauge('kvdb_max_clients', 'Redis最大客户端连接数', self.BASE_LABELS, registry=self.registry)
        self.blocked_clients = Gauge('kvdb_blocked_clients', 'Redis阻塞的客户端数量', self.BASE_LABELS, registry=self.registry)
        self.memory_used_bytes = Gauge('kvdb_memory_used_bytes', 'Redis已使用内存字节数', self.BASE_LABELS, registry=self.registry)
        self.memory_rss_bytes = Gauge('kvdb_memory_rss_bytes', 'Redis RSS内存字节数', self.BASE_LABELS, registry=self.registry)
        self.memory_max_bytes = Gauge('kvdb_memory_max_bytes', 'Redis最大可用内存字节数', self.BASE_LABELS, registry=self.registry)

        self.commands_processed = Gauge('kvdb_commands_processed', 'Redis处理的命令累计数', self.BASE_LABELS, registry=self.registry)
        self.commands_processed_total = Gauge('kvdb_commands_processed_total', '兼容旧面板的Redis处理命令累计数', self.BASE_LABELS, registry=self.registry)
        self.net_input_bytes = Gauge('kvdb_net_input_bytes', 'Redis接收的累计字节数', self.BASE_LABELS, registry=self.registry)
        self.net_input_bytes_total = Gauge('kvdb_net_input_bytes_total', '兼容旧面板的Redis接收累计字节数', self.BASE_LABELS, registry=self.registry)
        self.net_output_bytes = Gauge('kvdb_net_output_bytes', 'Redis发送的累计字节数', self.BASE_LABELS, registry=self.registry)
        self.net_output_bytes_total = Gauge('kvdb_net_output_bytes_total', '兼容旧面板的Redis发送累计字节数', self.BASE_LABELS, registry=self.registry)

        self.net_input_kbps = Gauge('kvdb_net_input_kbps', '进入Redis的网络流量(KB/s)', self.BASE_LABELS, registry=self.registry)
        self.net_output_kbps = Gauge('kvdb_net_output_kbps', '从Redis流出的网络流量(KB/s)', self.BASE_LABELS, registry=self.registry)
        self.db_keys = Gauge('kvdb_db_keys', 'Redis数据库中的键数量', self.BASE_LABELS + ['db'], registry=self.registry)
        self.db_keys_expiring = Gauge('kvdb_db_keys_expiring', 'Redis数据库中设置了过期时间的键数量', self.BASE_LABELS + ['db'], registry=self.registry)

        self.evicted_keys = Gauge('kvdb_evicted_keys', 'Redis因内存限制被驱逐的键累计数', self.BASE_LABELS, registry=self.registry)
        self.evicted_keys_total = Gauge('kvdb_evicted_keys_total', '兼容旧面板的驱逐键累计数', self.BASE_LABELS, registry=self.registry)
        self.commands = Gauge('kvdb_commands', 'Redis各命令的累计执行次数', self.BASE_LABELS + ['command'], registry=self.registry)
        self.commands_total = Gauge('kvdb_commands_total', '兼容旧面板的Redis各命令累计执行次数', self.BASE_LABELS + ['command'], registry=self.registry)

        self.slowlog_length = Gauge('kvdb_slowlog_length', 'Redis慢日志的长度', self.BASE_LABELS, registry=self.registry)
        self.connected_slaves = Gauge('kvdb_connected_slaves', 'Redis连接的从节点数量', self.BASE_LABELS, registry=self.registry)
        self.master_last_io_seconds_ago = Gauge('kvdb_master_last_io_seconds_ago', '主节点最后一次与从节点通信的时间（秒）', self.BASE_LABELS, registry=self.registry)
        self.master_repl_offset = Gauge('kvdb_master_repl_offset', '主节点复制偏移量', self.BASE_LABELS, registry=self.registry)
        self.master_link_status = Gauge('kvdb_master_link_status', 'master主从状态', self.BASE_LABELS, registry=self.registry)
        self.instantaneous_ops_per_sec = Gauge('kvdb_instantaneous_ops_per_sec', '当前每秒执行的命令数', self.BASE_LABELS, registry=self.registry)
        self.version = Gauge('kvdb_version', '兼容旧面板的版本号数字表示', self.BASE_LABELS, registry=self.registry)
        self.build_info = Gauge('kvdb_build_info', 'Redis/KVRocks版本信息', self.BASE_LABELS + ['engine', 'version'], registry=self.registry)
        self.port = Gauge('kvdb_port', 'Redis监听端口', self.BASE_LABELS, registry=self.registry)
        self.engine_type = Gauge('kvdb_engine_type', '引擎类型(1=Redis, 2=KVRocks, 3=Pika)', self.BASE_LABELS, registry=self.registry)

        self.db_used_bytes = Gauge('kvdb_db_used_bytes', '硬盘存储类型的引擎存储数据所占硬盘字节数', self.BASE_LABELS, registry=self.registry)
        self.disk_used_bytes = Gauge('kvdb_disk_used_bytes', '当前硬盘总使用字节数', self.BASE_LABELS, registry=self.registry)
        self.disk_max_bytes = Gauge('kvdb_disk_max_bytes', '当前硬盘总字节数', self.BASE_LABELS, registry=self.registry)

    @staticmethod
    def _instance_ip(instance):
        if instance.count(':') == 1:
            return instance.split(':', 1)[0]
        return instance.rsplit(':', 1)[0] if ':' in instance else instance

    @staticmethod
    def _engine_name(node_type):
        return {1: 'redis', 2: 'kvrocks', 3: 'pika'}.get(node_type, 'unknown')

    @staticmethod
    def _version_number(version):
        digits = ''.join(ch for ch in str(version) if ch.isdigit())
        return int(digits) if digits else 0

    def _labels(self, instance, info, sentinel_name):
        master_name = info.get('master_name', 'unknown')
        role = info.get('node_role', 'unknown')
        return {
            'db_instance': instance,
            'db_instance_ip': self._instance_ip(instance),
            'group_name': master_name,
            'role': role,
            'sentinel_name': sentinel_name,
        }

    def collect_scrape_metrics(self, sentinel_name, success, duration, sentinel_status=None):
        self.scrape_success.labels(sentinel_name=sentinel_name).set(1 if success else 0)
        self.scrape_duration_seconds.labels(sentinel_name=sentinel_name).set(duration)

        for status in sentinel_status or []:
            self.sentinel_up.labels(
                sentinel_name=sentinel_name,
                sentinel_host=status.get('host', 'unknown'),
                sentinel_port=str(status.get('port', 'unknown')),
            ).set(status.get('up', 0))

    def collect_metrics(self, redis_info_dict, sentinel_name):
        """从Redis信息收集指标"""
        for instance, info in redis_info_dict.items():
            labels = self._labels(instance, info, sentinel_name)
            node_type = info.get('type', 1)
            is_kvrocks = node_type == 2

            self.up.labels(**labels).set(info.get('up', 1))
            if info.get('up') == 0:
                continue

            is_master = 1 if labels['role'] == 'master' else 0
            self.node_role.labels(**labels).set(is_master)
            self.engine_type.labels(**labels).set(node_type)
            self.uptime_in_seconds.labels(**labels).set(info.get('uptime_in_seconds', 0))

            if 'connected_clients' in info:
                self.connected_clients.labels(**labels).set(info['connected_clients'])
            if 'maxclients' in info:
                self.max_clients.labels(**labels).set(info['maxclients'])
            if 'blocked_clients' in info:
                self.blocked_clients.labels(**labels).set(info['blocked_clients'])
            if 'used_memory' in info:
                self.memory_used_bytes.labels(**labels).set(info['used_memory'])
            if 'used_memory_rss' in info:
                self.memory_rss_bytes.labels(**labels).set(info['used_memory_rss'])

            max_memory = 0 if is_kvrocks else info.get('maxmemory', 0)
            self.memory_max_bytes.labels(**labels).set(max_memory)

            if 'total_commands_processed' in info:
                value = info['total_commands_processed']
                self.commands_processed.labels(**labels).set(value)
                self.commands_processed_total.labels(**labels).set(value)

            if 'total_net_input_bytes' in info:
                value = info['total_net_input_bytes']
                self.net_input_bytes.labels(**labels).set(value)
                self.net_input_bytes_total.labels(**labels).set(value)

            if 'total_net_output_bytes' in info:
                value = info['total_net_output_bytes']
                self.net_output_bytes.labels(**labels).set(value)
                self.net_output_bytes_total.labels(**labels).set(value)

            if 'instantaneous_input_kbps' in info:
                self.net_input_kbps.labels(**labels).set(info['instantaneous_input_kbps'])
            if 'instantaneous_output_kbps' in info:
                self.net_output_kbps.labels(**labels).set(info['instantaneous_output_kbps'])

            for key, value in info.items():
                if key.startswith('db') and isinstance(value, dict):
                    if 'keys' in value:
                        self.db_keys.labels(**labels, db=key).set(value['keys'])
                    if 'expires' in value:
                        self.db_keys_expiring.labels(**labels, db=key).set(value['expires'])

            if 'evicted_keys' in info:
                value = info['evicted_keys']
                self.evicted_keys.labels(**labels).set(value)
                self.evicted_keys_total.labels(**labels).set(value)

            for cmd, stats in info.get('commandstats', {}).items():
                cmd_name = cmd.replace('cmdstat_', '')
                if 'calls' in stats:
                    self.commands.labels(**labels, command=cmd_name).set(stats['calls'])
                    self.commands_total.labels(**labels, command=cmd_name).set(stats['calls'])

            if 'slowlog_len' in info:
                self.slowlog_length.labels(**labels).set(info['slowlog_len'])
            if 'connected_slaves' in info:
                self.connected_slaves.labels(**labels).set(info['connected_slaves'])
            if 'master_last_io_seconds_ago' in info:
                self.master_last_io_seconds_ago.labels(**labels).set(info['master_last_io_seconds_ago'])
            if 'master_repl_offset' in info:
                self.master_repl_offset.labels(**labels).set(info['master_repl_offset'])
            if 'master_link_status' in info:
                self.master_link_status.labels(**labels).set(1 if info['master_link_status'] == 'up' else 0)
            if 'instantaneous_ops_per_sec' in info:
                self.instantaneous_ops_per_sec.labels(**labels).set(info['instantaneous_ops_per_sec'])

            if is_kvrocks:
                if 'used_db_size' in info:
                    self.db_used_bytes.labels(**labels).set(info['used_db_size'])
                if 'used_disk_size' in info:
                    self.disk_used_bytes.labels(**labels).set(info['used_disk_size'])
                if 'disk_capacity' in info:
                    self.disk_max_bytes.labels(**labels).set(info['disk_capacity'])

            version_str = info.get('version') if is_kvrocks else info.get('redis_version', 'unknown')
            self.version.labels(**labels).set(self._version_number(version_str))
            self.build_info.labels(**labels, engine=self._engine_name(node_type), version=str(version_str)).set(1)

            if 'tcp_port' in info:
                self.port.labels(**labels).set(info['tcp_port'])

    def get_metrics(self):
        """获取指标数据"""
        return generate_latest(self.registry)

    def get_content_type(self):
        """获取内容类型"""
        return CONTENT_TYPE_LATEST
