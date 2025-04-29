import logging
import os
import yaml

class Config:
    _config = None
    
    @classmethod
    def load_config(cls, config_file='config.yaml'):
        """加载配置文件"""
        if cls._config is None:
            # 尝试在多个位置查找配置文件
            possible_paths = [
                config_file,  # 1. 直接使用提供的路径
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), config_file),  # 2. 相对于项目根目录
                os.path.join('/app', config_file)  # 3. Docker环境中的路径
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        cls._config = yaml.safe_load(f)
                    logging.info(f"成功从 {path} 加载配置")
                    break
            
            if cls._config is None:
                raise FileNotFoundError(f"无法找到配置文件。尝试查找的路径: {', '.join(possible_paths)}")
                
        return cls._config
    
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
        default_password = sentinel_config.get('default_password', '')
        
        result = {
            'default_password': default_password,
            'master_groups': sentinel_config.get('master_groups', {})
        }
        
        # 处理sentinel_hosts字段，适应新配置结构
        if 'sentinel_hosts' in sentinel_config:
            # 处理字符串格式的"host:port"
            hosts = []
            for host_entry in sentinel_config['sentinel_hosts']:
                if isinstance(host_entry, str) and ':' in host_entry:
                    # 格式为 "host:port"
                    host, port = host_entry.split(':', 1)
                    hosts.append({
                        'host': host,
                        'port': int(port)
                    })
                elif isinstance(host_entry, dict) and 'host' in host_entry and 'port' in host_entry:
                    # 兼容旧格式 {host: "...", port: ...}
                    hosts.append(host_entry)
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