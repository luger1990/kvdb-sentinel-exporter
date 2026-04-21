import logging
import os
import yaml


class ConfigError(ValueError):
    """Raised when the YAML configuration is invalid."""


class Config:
    _config = None
    _config_path = None
    DEFAULT_BLOCKED_COMMANDS = [
        'acl',
        'bgrewriteaof',
        'bgsave',
        'config',
        'debug',
        'failover',
        'flushall',
        'flushdb',
        'lastsave',
        'migrate',
        'module',
        'monitor',
        'replicaof',
        'restore',
        'save',
        'shutdown',
        'slaveof',
        'sync',
    ]

    @staticmethod
    def _resolve_env(value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_name = value[2:-1]
            return os.environ.get(env_name, "")
        return value

    @staticmethod
    def _as_int(value, field_name, minimum=None):
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} 必须是整数") from exc

        if minimum is not None and result < minimum:
            raise ConfigError(f"{field_name} 必须大于等于 {minimum}")
        return result

    @staticmethod
    def _as_float(value, field_name, minimum=None):
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{field_name} 必须是数字") from exc

        if minimum is not None and result < minimum:
            raise ConfigError(f"{field_name} 必须大于等于 {minimum}")
        return result
    
    @classmethod
    def load_config(cls, config_file='config.yaml', force_reload=False):
        """加载配置文件"""
        if cls._config is None or force_reload:
            # 尝试在多个位置查找配置文件
            possible_paths = [
                config_file,  # 1. 直接使用提供的路径
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_file),  # 2. 相对于项目根目录
                os.path.join('/app', config_file)  # 3. Docker环境中的路径
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        loaded_config = yaml.safe_load(f) or {}
                    cls._config = cls._validate_config(loaded_config)
                    cls._config_path = path
                    logging.info(f"成功从 {path} 加载配置")
                    break
            
            if cls._config is None:
                raise FileNotFoundError(f"无法找到配置文件。尝试查找的路径: {', '.join(possible_paths)}")
                
        return cls._config

    @classmethod
    def reload_config(cls, config_file=None):
        """强制重新加载配置文件。"""
        return cls.load_config(config_file or cls._config_path or 'config.yaml', force_reload=True)

    @classmethod
    def _validate_config(cls, config):
        if not isinstance(config, dict):
            raise ConfigError("配置文件顶层必须是 YAML 对象")

        sentinels = config.get('sentinels', {})
        if sentinels is None:
            sentinels = {}
        if not isinstance(sentinels, dict):
            raise ConfigError("sentinels 必须是对象")

        for sentinel_name, sentinel_config in sentinels.items():
            if not isinstance(sentinel_config, dict):
                raise ConfigError(f"sentinels.{sentinel_name} 必须是对象")

            hosts = sentinel_config.get('sentinel_hosts', [])
            if not isinstance(hosts, list):
                raise ConfigError(f"sentinels.{sentinel_name}.sentinel_hosts 必须是列表")

            for index, host_entry in enumerate(hosts):
                field = f"sentinels.{sentinel_name}.sentinel_hosts[{index}]"
                if isinstance(host_entry, str):
                    if ':' not in host_entry:
                        raise ConfigError(f"{field} 必须使用 host:port 格式")
                    _, port = host_entry.rsplit(':', 1)
                    cls._as_int(port, f"{field}.port", minimum=1)
                elif isinstance(host_entry, dict):
                    if 'host' not in host_entry or 'port' not in host_entry:
                        raise ConfigError(f"{field} 必须包含 host 和 port")
                    cls._as_int(host_entry['port'], f"{field}.port", minimum=1)
                else:
                    raise ConfigError(f"{field} 必须是字符串或对象")

        metrics = config.setdefault('metrics', {})
        if not isinstance(metrics, dict):
            raise ConfigError("metrics 必须是对象")
        metrics['thread_pool_size'] = cls._as_int(metrics.get('thread_pool_size', 10), 'metrics.thread_pool_size', minimum=1)
        metrics['connect_timeout'] = cls._as_float(metrics.get('connect_timeout', 3), 'metrics.connect_timeout', minimum=0.1)
        metrics['read_timeout'] = cls._as_float(metrics.get('read_timeout', 5), 'metrics.read_timeout', minimum=0.1)
        metrics['discovery_ttl'] = cls._as_int(metrics.get('discovery_ttl', 30), 'metrics.discovery_ttl', minimum=1)

        web_ui = config.setdefault('web_ui', {})
        if not isinstance(web_ui, dict):
            raise ConfigError("web_ui 必须是对象")
        web_ui['refresh_interval'] = cls._as_int(web_ui.get('refresh_interval', 30), 'web_ui.refresh_interval', minimum=1)
        web_ui['analytics_enabled'] = bool(web_ui.get('analytics_enabled', False))

        terminal = config.setdefault('terminal', {})
        if not isinstance(terminal, dict):
            raise ConfigError("terminal 必须是对象")
        terminal['enabled'] = bool(terminal.get('enabled', True))
        blocked_commands = terminal.get('blocked_commands', cls.DEFAULT_BLOCKED_COMMANDS)
        if not isinstance(blocked_commands, list):
            raise ConfigError("terminal.blocked_commands 必须是列表")
        terminal['blocked_commands'] = sorted({str(command).strip().lower() for command in blocked_commands if str(command).strip()})

        return config
    
    @classmethod
    def get_config(cls, config_file=None):
        """获取配置信息"""
        if cls._config is None:
            if config_file:
                return cls.load_config(config_file)
            else:
                return cls.load_config()
        return cls._config
    
    @classmethod
    def get_sentinel_config(cls, sentinel_name):
        """获取指定哨兵的配置信息"""
        config = cls.get_config()
        
        if 'sentinels' not in config or sentinel_name not in config['sentinels']:
            return None
        
        sentinel_config = config['sentinels'][sentinel_name]
        
        # 获取该sentinel组的默认密码，如果未配置则使用空字符串
        default_password = cls._resolve_env(sentinel_config.get('default_password', ''))
        if 'default_password_env' in sentinel_config:
            default_password = os.environ.get(str(sentinel_config.get('default_password_env')), default_password)

        master_groups = sentinel_config.get('master_groups', {})
        for master_config in master_groups.values():
            if isinstance(master_config, dict):
                if 'password' in master_config:
                    master_config['password'] = cls._resolve_env(master_config.get('password', ''))
                if 'password_env' in master_config:
                    master_config['password'] = os.environ.get(str(master_config.get('password_env')), master_config.get('password', ''))
        
        result = {
            'default_password': default_password,
            'master_groups': master_groups
        }
        
        # 处理sentinel_hosts字段，适应新配置结构
        if 'sentinel_hosts' in sentinel_config:
            # 处理字符串格式的"host:port"
            hosts = []
            for host_entry in sentinel_config['sentinel_hosts']:
                if isinstance(host_entry, str) and ':' in host_entry:
                    # 格式为 "host:port"
                    host, port = host_entry.rsplit(':', 1)
                    hosts.append({
                        'host': host,
                        'port': int(port)
                    })
                elif isinstance(host_entry, dict) and 'host' in host_entry and 'port' in host_entry:
                    # 兼容旧格式 {host: "...", port: ...}
                    hosts.append({
                        'host': host_entry['host'],
                        'port': int(host_entry['port'])
                    })
            result['sentinel_hosts'] = hosts
        else:
            # 向后兼容，如果没有sentinel_hosts字段但有直接的主机列表
            hosts = []
            for item in sentinel_config:
                if isinstance(item, dict) and 'host' in item and 'port' in item:
                    hosts.append(item)
            result['sentinel_hosts'] = hosts
        
        return result
    
    @classmethod
    def get_all_sentinel_names(cls):
        """获取所有哨兵组名称"""
        config = cls.get_config()
        if 'sentinels' not in config:
            return []
        
        return list(config['sentinels'].keys())
    
    @classmethod
    def get_metrics_config(cls):
        """获取指标收集配置"""
        config = cls.get_config()
        return config.get('metrics', {})
    
    @classmethod
    def get_web_ui_config(cls):
        """获取Web UI配置"""
        config = cls.get_config()
        return config.get('web_ui', {}) 

    @classmethod
    def get_terminal_config(cls):
        """获取Web Terminal配置"""
        config = cls.get_config()
        return config.get('terminal', {})
