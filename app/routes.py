from flask import Blueprint, current_app, render_template, request, Response, jsonify
from .sentinel import RedisSentinel
from .metrics import RedisMetricsCollector
from .config import Config
import logging
import shlex
import time
from collections import OrderedDict

bp = Blueprint('routes', __name__)
_sentinel_clients = {}
MAX_TERMINAL_OUTPUT_LENGTH = 20000


def get_sentinel_client(sentinel_name):
    """按哨兵组缓存客户端，避免每次请求重复建立Sentinel连接。"""
    if Config.get_sentinel_config(sentinel_name) is None:
        raise KeyError(f"Sentinel配置 '{sentinel_name}' 不存在")

    sentinel = _sentinel_clients.get(sentinel_name)
    if sentinel is None:
        sentinel = RedisSentinel(sentinel_name)
        _sentinel_clients[sentinel_name] = sentinel
    return sentinel


def build_node_data(info):
    is_kvrocks = info.get('type') == 2 or info.get('is_kvrocks', False)
    maxmemory = 0
    if not is_kvrocks:
        maxmemory = info.get('maxmemory', 0)
        try:
            if int(maxmemory) <= 0:
                maxmemory = info.get('total_system_memory', 0)
        except (TypeError, ValueError):
            maxmemory = 0

    total_keys = info.get('total_keys', 0)
    return {
        'master_name': info.get('master_name', 'unknown'),
        'host': info.get('host', 'unknown'),
        'port': info.get('port', 'unknown'),
        'role': info.get('node_role', 'unknown'),
        'up': info.get('up', 1),
        'error': info.get('error', ''),
        'connected_clients': info.get('connected_clients', 0),
        'used_memory_human': info.get('used_memory_human', '0B'),
        'total_system_memory_human': info.get('total_system_memory_human', '0B'),
        'used_memory': info.get('used_memory', 0),
        'maxmemory': maxmemory,
        'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
        'uptime_in_seconds': info.get('uptime_in_seconds', 0),
        'uptime_in_days': info.get('uptime_in_days', 0),
        'version': info.get('version', 'unknown') if is_kvrocks else info.get('redis_version', 'unknown'),
        'is_kvrocks': is_kvrocks,
        'type': info.get('type', 1),
        'total_keys': total_keys,
        'disk_capacity': info.get('disk_capacity', 0),
        'used_disk_size': info.get('used_disk_size', 0),
    }


def parse_redis_command(command):
    command = (command or '').strip()
    if not command:
        raise ValueError("命令不能为空")
    if len(command) > 4096:
        raise ValueError("命令过长")

    try:
        parts = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"命令解析失败: {exc}") from exc

    if not parts:
        raise ValueError("命令不能为空")
    return parts


def validate_terminal_command(command_parts):
    terminal_config = Config.get_terminal_config()
    if not terminal_config.get('enabled', True):
        raise PermissionError("Web Terminal 已禁用")

    command_name = command_parts[0].lower()
    blocked_commands = set(terminal_config.get('blocked_commands', []))
    if command_name in blocked_commands:
        raise PermissionError(f"命令 '{command_parts[0]}' 已被禁止")


def format_redis_result(value):
    if value is None:
        return "(nil)"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (bytes, bytearray)):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        lines = []
        for key, item in value.items():
            lines.append(f"{format_redis_result(key)}: {format_redis_result(item)}")
        return "\n".join(lines)
    if isinstance(value, (list, tuple, set)):
        if not value:
            return "(empty list or set)"
        lines = []
        for index, item in enumerate(value, start=1):
            item_text = format_redis_result(item)
            if "\n" in item_text:
                lines.append(f"{index})")
                lines.extend(f"   {line}" for line in item_text.splitlines())
            else:
                lines.append(f"{index}) {item_text}")
        return "\n".join(lines)

    return str(value)

@bp.route('/')
def index():
    """首页 - 显示所有可用的哨兵组"""
    sentinel_names = Config.get_all_sentinel_names()
    return render_template('index.html', sentinel_names=sentinel_names)


@bp.route('/favicon.ico')
def favicon():
    """浏览器默认favicon入口"""
    return current_app.send_static_file('favicon.ico')

@bp.route('/<sentinel_name>/metrics')
def metrics(sentinel_name):
    """Prometheus指标接口"""
    try:
        # 创建新的指标收集器实例，避免线程安全问题
        metrics_collector = RedisMetricsCollector()
        
        # 获取Redis Sentinel客户端
        sentinel = get_sentinel_client(sentinel_name)
        
        # 收集所有Redis节点信息
        redis_info = sentinel.collect_all_redis_info()
        
        # 收集Prometheus指标
        metrics_collector.collect_scrape_metrics(
            sentinel_name,
            sentinel.last_scrape_success,
            sentinel.last_scrape_duration,
            sentinel.sentinel_status,
        )
        metrics_collector.collect_metrics(redis_info, sentinel_name)
        
        # 返回指标数据
        return Response(metrics_collector.get_metrics(), 
                       content_type=metrics_collector.get_content_type())
    except KeyError as e:
        logging.warning("获取指标失败: %s", str(e))
        return jsonify({'error': str(e)}), 404
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
        sentinel = get_sentinel_client(sentinel_name)
        
        # 收集所有Redis节点信息
        redis_info = sentinel.collect_all_redis_info()
        
        # 准备模板数据
        masters = {}
        slaves = {}
        
        # 整理主节点和从节点数据
        for info in redis_info.values():
            master_name = info.get('master_name', 'unknown')
            role = info.get('node_role', 'unknown')
            node_data = build_node_data(info)
            
            if role == 'master':
                if master_name not in masters:
                    masters[master_name] = []
                masters[master_name].append(node_data)
            else:
                if master_name not in slaves:
                    slaves[master_name] = []
                slaves[master_name].append(node_data)
        
        # 使用有序字典保持顺序
        sorted_masters = OrderedDict()
        for master_name in sorted(masters.keys(), key=lambda x: int(x.split('-')[-1]) if x.split('-')[-1].isdigit() else 0):
            sorted_masters[master_name] = masters[master_name]

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
    except KeyError as e:
        logging.warning("获取节点详情数据失败: %s", str(e))
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logging.error(f"获取节点详情数据失败: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/<sentinel_name>/nodes')
def nodes(sentinel_name):
    """API - 返回所有Redis节点的JSON数据"""
    try:
        # 获取Redis Sentinel客户端
        sentinel = get_sentinel_client(sentinel_name)
        
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
    except KeyError as e:
        logging.warning("获取节点信息失败: %s", str(e))
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logging.error(f"获取节点信息失败: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/<sentinel_name>/terminal/execute', methods=['POST'])
def terminal_execute(sentinel_name):
    """API - 在指定Redis节点执行单条Redis命令"""
    try:
        payload = request.get_json(silent=True) or {}
        host = str(payload.get('host', '')).strip()
        port = int(payload.get('port'))
        master_name = str(payload.get('master_name', '')).strip()
        command = str(payload.get('command', '')).strip()

        if not host or not master_name:
            return jsonify({'error': 'host 和 master_name 不能为空'}), 400

        command_parts = parse_redis_command(command)
        validate_terminal_command(command_parts)

        sentinel = get_sentinel_client(sentinel_name)
        if not sentinel.is_known_node(host, port, master_name):
            return jsonify({'error': '目标Redis节点不属于当前Sentinel发现结果'}), 403

        started_at = time.time()
        result = sentinel.execute_redis_command(host, port, master_name, command_parts)
        output = format_redis_result(result)
        truncated = False
        if len(output) > MAX_TERMINAL_OUTPUT_LENGTH:
            output = output[:MAX_TERMINAL_OUTPUT_LENGTH] + "\n... output truncated ..."
            truncated = True

        return jsonify({
            'ok': True,
            'output': output,
            'truncated': truncated,
            'duration_ms': round((time.time() - started_at) * 1000, 2),
        })
    except KeyError as e:
        logging.warning("Redis Terminal执行失败: %s", str(e))
        return jsonify({'error': str(e)}), 404
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403
    except (TypeError, ValueError) as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.warning("Redis Terminal执行失败: %s", str(e))
        return jsonify({'error': str(e)}), 500


@bp.route('/<sentinel_name>/terminal')
def terminal_page(sentinel_name):
    """Web UI - 独立Redis Terminal页面"""
    try:
        sentinel = get_sentinel_client(sentinel_name)
        host = str(request.args.get('host', '')).strip()
        port = int(request.args.get('port'))
        master_name = str(request.args.get('master_name', '')).strip()
        role = str(request.args.get('role', 'unknown')).strip() or 'unknown'

        if not sentinel.is_known_node(host, port, master_name):
            return render_template('error.html', error='目标Redis节点不属于当前Sentinel发现结果'), 403

        return render_template(
            'terminal.html',
            sentinel_name=sentinel_name,
            host=host,
            port=port,
            master_name=master_name,
            role=role,
        )
    except KeyError as e:
        logging.warning("打开Redis Terminal失败: %s", str(e))
        return render_template('error.html', error=str(e)), 404
    except (TypeError, ValueError) as e:
        return render_template('error.html', error=str(e)), 400
    except Exception as e:
        logging.warning("打开Redis Terminal失败: %s", str(e))
        return render_template('error.html', error=str(e)), 500


@bp.route('/api/health', methods=['GET'])
def health_check():
    return Response("health", status=200, mimetype='text/plain')

@bp.errorhandler(404)
def page_not_found(e):
    """404错误页面"""
    return render_template('404.html'), 404

@bp.errorhandler(500)
def internal_server_error(e):
    """500错误页面"""
    return render_template('500.html'), 500
