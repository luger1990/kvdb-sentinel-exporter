# KVDB Sentinel Exporter

KVDB Sentinel Exporter is a Python and Flask-based tool for monitoring Redis Sentinel clusters, providing Prometheus metrics and a web interface.

[中文文档](README_CN.md)

## Features

- Support for multiple Redis sentinel groups
- Global and master-specific Redis password configuration
- Prometheus metrics endpoint
- User-friendly web interface for Redis node status
- Multi-threaded parallel collection of Redis metrics
- Support for both KVRocks and Redis engines

## Installation

### Requirements

- Python 3.9+
- Redis 5.0+
- Flask 2.3+
- Prometheus Client

### From Source

```bash
# Clone repository
git clone https://github.com/luger1990/kvdb-sentinel-exporter.git
cd kvdb-sentinel-exporter

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
cp config.yaml config.local.yaml  # Modify configuration as needed
```

### Using Docker

```bash
# Use pre-built image
docker pull luger1990/kvdb-sentinel-exporter

# Or build from Dockerfile
docker build -t kvdb-sentinel-exporter .

# Run container
docker run -d -p 16379:16379 -v $(pwd)/config.yaml:/app/config.yaml kvdb-sentinel-exporter
```

## Configuration

Configuration uses YAML format, with the default path being `config.yaml`. You can customize the config file path using the `CONFIG_PATH` environment variable.

### Configuration Example

```yaml
# KVDB Sentinel Exporter 配置文件

# Redis哨兵配置
sentinels:
  # 第一个哨兵组
  redis-group-1:
    # 本组Redis默认密码（可选，当master没有单独指定密码时使用此密码）
    default_password: "ce67a0a422243742573ac12024c39f82"
    sentinel_hosts:
      - "127.0.0.1:26379"
      - "127.0.0.1:26380"
      - "127.0.0.1:26391"
    # 为特定master_name指定密码配置（会覆盖默认密码）
    master_groups:
      # 示例：为特定master_name设置专用密码
      kvrocks-group-1:
        password: "cfc44dfc4f1a3f36400740680fd8c30c"
      # 注意：未在此处列出的master_name将使用default_password
  
  # 第二个哨兵组
  redis-group-2:
    # 本组Redis默认密码（可选）
    default_password: ""
    sentinel_hosts:
      - "127.0.0.1:16379"
      - "127.0.0.1:16380"
      - "127.0.0.1:16391"

# 指标收集配置
metrics:
  # 收集线程池大小
  thread_pool_size: 10
  # 连接超时时间（秒）
  connect_timeout: 3
  # 读取超时时间（秒）
  read_timeout: 5

# Web UI配置
web_ui:
  # 刷新间隔（秒）
  refresh_interval: 30 
```

### Environment Variables

Configuration can be set via `.env` file or environment variables:

- `DEBUG`: Enable debug mode (default: false)
- `HOST`: Listen address (default: 0.0.0.0)
- `PORT`: Listen port (default: 16379)
- `CONFIG_PATH`: Config file path (default: config.yaml)

## Usage

### Starting the Service

```bash
# Run directly
python run.py

# Specify config file
python run.py /path/to/config.yaml

# Use environment variable for config
CONFIG_PATH=/path/to/config.yaml python run.py
```

### Accessing the Web Interface

Visit `http://localhost:16379/` to view the sentinel group list

Visit `http://localhost:16379/<sentinel_name>/info` to view the Redis node status for a specific sentinel group

### Prometheus Metrics

Prometheus metrics endpoint: `http://localhost:16379/<sentinel_name>/metrics`

Key metrics include:

- `kvdb_up`: Redis instance online status
- `kvdb_role`: Redis node role
- `kvdb_memory_used_bytes`: Redis memory usage
- `kvdb_connected_clients`: Number of client connections
- `kvdb_commands_processed_total`: Total processed commands
- `kvdb_instantaneous_ops_per_sec`: Operations per second
- `kvdb_engine_type`: Engine type (Redis/KVRocks)

## Prometheus Configuration Example

```yaml
scrape_configs:
  - job_name: 'redis_sentinel'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:16379']
    metrics_path: '/nct-redis-sentinel/metrics'
```

## Development Mode and Hot Reload

For improved development efficiency, this project supports hot reloading, which automatically restarts the server when code or templates are modified.

### Setting Up Development Environment

1. Install development dependencies
   ```bash
   pip install -r requirements.txt
   ```

2. Create development environment configuration file
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file to enable debug mode
   ```
   DEBUG=true
   ```

4. Start the server
   ```bash
   python run.py
   ```

### Hot Reload Features

When `DEBUG=true` is set, the application automatically enables:

1. **Auto-reload**: The application reloads when Python files, HTML templates, JavaScript, or CSS files are modified
2. **No static resource caching**: The browser always gets the latest version of static resources
3. **Debug toolbar**: Displays a debug toolbar in the web interface with request, route, and configuration information

Monitored file extensions include:
- `.py` (Python source files)
- `.html` (HTML templates)
- `.js` (JavaScript files)
- `.css` (CSS stylesheets)
- `.yaml` and `.yml` (Configuration files)

## License

MIT 