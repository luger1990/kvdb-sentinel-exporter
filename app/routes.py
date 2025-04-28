from flask import Blueprint, render_template, request, Response, jsonify, current_app
from .sentinel import RedisSentinel
from .metrics import RedisMetricsCollector
from .config import Config
import logging
import time
from collections import OrderedDict

bp = Blueprint('routes', __name__)

@bp.route('/')
def index():
    """首页 - 显示所有可用的哨兵组"""
    sentinel_names = Config.get_all_sentinel_names()
    return render_template('index.html', sentinel_names=sentinel_names)

@bp.route('/<sentinel_name>/metrics')
def metrics(sentinel_name):
    """Prometheus指标接口"""
    try:
        # 创建新的指标收集器实例，避免线程安全问题
        metrics_collector = RedisMetricsCollector()
        
        # 获取Redis Sentinel客户端
        sentinel = RedisSentinel(sentinel_name)
        
        # 收集所有Redis节点信息
        redis_info = sentinel.collect_all_redis_info()
        
        # 收集Prometheus指标
        metrics_collector.collect_metrics(redis_info)
        
        # 返回指标数据
        return Response(metrics_collector.get_metrics(), 
                       content_type=metrics_collector.get_content_type())
    except Exception as e:
        logging.error(f"获取指标失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/<sentinel_name>/info')
def info(sentinel_name):
    """Web UI - 显示哨兵组下所有Redis节点信息"""
    try:
        # 获取Web UI配置
        web_ui_config = Config.get_web_ui_config()
        refresh_interval = web_ui_config.get('refresh_interval', 30)
        
        return render_template('info.html', 
                              sentinel_name=sentinel_name,
                              refresh_interval=refresh_interval)
    except Exception as e:
        logging.error(f"获取信息页面失败: {str(e)}")
        return render_template('error.html', error=str(e))

@bp.route('/<sentinel_name>/info/data')
def info_data(sentinel_name):
    """API - 返回Redis节点详细信息的JSON数据，用于AJAX请求"""
    try:
        # 获取Redis Sentinel客户端
        sentinel = RedisSentinel(sentinel_name)
        
        # 收集所有Redis节点信息
        redis_info = sentinel.collect_all_redis_info()
        
        # 准备模板数据
        masters = {}
        slaves = {}
        
        # 整理主节点和从节点数据
        for instance, info in redis_info.items():
            master_name = info.get('master_name', 'unknown')
            role = info.get('node_role', 'unknown')
            is_kvrocks = info.get('is_kvrocks', False)
            
            # 添加type字段：1=Redis, 2=KVRocks, 3=Pika
            node_type = 2 if is_kvrocks else 1
            # 未来可以在这里添加Pika等其他引擎类型的判断
            # 例如：if 'pika_feature' in info: node_type = 3

            maxmemory = 0
            if not is_kvrocks:
                maxmemory = info.get('maxmemory', 0)
                if int(maxmemory) <= 0:
                    maxmemory = info.get('total_system_memory')

            # 计算键总数
            total_keys = info.get('total_keys', 0)
            if not total_keys:
                total_keys = 0
                for key, value in info.items():
                    if key.startswith('db') and isinstance(value, dict) and 'keys' in value:
                        try:
                            total_keys += int(value['keys'])
                        except (ValueError, TypeError):
                            logging.warning(f"处理键数量时出错，无效值: {value['keys']}")

            node_data = {
                'master_name': master_name,  # 添加master_name到节点数据中
                'host': info.get('host', 'unknown'),
                'port': info.get('port', 'unknown'),
                'role': role,
                'connected_clients': info.get('connected_clients', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'total_system_memory_human': info.get('total_system_memory_human', '0B'),
                'used_memory': info.get('used_memory', 0),
                'maxmemory': maxmemory,
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
                'uptime_in_seconds': info.get('uptime_in_seconds', 0),
                'uptime_in_days': info.get('uptime_in_days', 0),
                'version': info.get('version', 'unknown') if is_kvrocks else info.get('redis_version', 'unknown'),
                'is_kvrocks': info.get('is_kvrocks', False),  # 保留兼容性
                'type': node_type,  # 新增type字段
                'total_keys': total_keys,
                'disk_capacity': info.get('disk_capacity', ''),
                'used_disk_size': info.get('used_disk_size', ''),
            }
            
            if role == 'master':
                if master_name not in masters:
                    masters[master_name] = []
                masters[master_name].append(node_data)
            else:
                if master_name not in slaves:
                    slaves[master_name] = []
                slaves[master_name].append(node_data)
        
        # 将masters字典按照端口号排序
        print(masters.keys())
        print(sorted(masters.keys(), key=lambda x: int(x.split('-')[-1]) if x.split('-')[-1].isdigit() else 0))
        
        # 使用有序字典保持顺序
        sorted_masters = OrderedDict()
        for master_name in sorted(masters.keys(), key=lambda x: int(x.split('-')[-1]) if x.split('-')[-1].isdigit() else 0):
            sorted_masters[master_name] = masters[master_name]
        
        print('--------------------------------')
        print(sorted_masters)
        
        # 创建新的nodes数组结构，每个主节点包含对应的从节点
        nodes = []
        
        # 将主节点和从节点整合进新结构
        for master_name, master_nodes in sorted_masters.items():
            # 为每个主节点组创建一个节点组对象
            for master_node in master_nodes:
                # 复制主节点数据
                node_group = {**master_node}
                
                # 添加slaves字段，包含所有对应的从节点
                node_group['slaves'] = slaves.get(master_name, [])
                
                # 添加到nodes数组
                nodes.append(node_group)
        
        # 使用有序字典创建返回数据
        response_data = OrderedDict()
        response_data['sentinel_name'] = sentinel_name
        response_data['nodes'] = nodes  # 使用新的整合结构
        response_data['timestamp'] = int(time.time())
        
        # 返回JSON响应
        from flask import json
        return Response(
            json.dumps(response_data),
            mimetype='application/json'
        )
    except Exception as e:
        logging.error(f"获取节点详情数据失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/<sentinel_name>/nodes')
def nodes(sentinel_name):
    """API - 返回所有Redis节点的JSON数据"""
    try:
        # 获取Redis Sentinel客户端
        sentinel = RedisSentinel(sentinel_name)
        
        # 获取所有主节点
        masters = sentinel.get_all_masters()
        
        # 获取所有从节点
        slaves_by_master = sentinel.get_all_slaves()
        
        # 准备返回数据
        result = {
            'sentinel_name': sentinel_name,
            'masters': {},
            'slaves': {}
        }
        
        # 整理主节点数据
        for master_name, master_info in masters.items():
            result['masters'][master_name] = {
                'host': master_info.get('ip', 'unknown'),
                'port': master_info.get('port', 'unknown'),
                'status': master_info.get('status', 'unknown')
            }
        
        # 整理从节点数据
        for master_name, slaves in slaves_by_master.items():
            result['slaves'][master_name] = []
            for slave in slaves:
                slave_info = {
                    'host': slave.get('ip', 'unknown'),
                    'port': slave.get('port', 'unknown'),
                    'status': slave.get('status', 'unknown')
                }
                result['slaves'][master_name].append(slave_info)
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"获取节点信息失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.errorhandler(404)
def page_not_found(e):
    """404错误页面"""
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    """500错误页面"""
    return render_template('500.html'), 500