# KVDB Sentinel Exporter
<p align="center" style="text-align:center;">
   <img alt="KVDB Logo" height="200" src="https://github.com/luger1990/kvdb-sentinel-exporter/raw/main/static/images/logo.png" title="KVDB" width="200"/>
</p>
KVDB Sentinel Exporter是一个基于Python和Flask的工具，用于监控Redis Sentinel集群并提供Prometheus指标和Web界面。

[English Documentation](https://github.com/luger1990/kvdb-sentinel-exporter/blob/main/README.md) 

[管理平台预览地址](https://kvdb.luger.me/)

## 功能特点

- 支持配置多个Redis哨兵组
- 支持全局和特定master_name的Redis密码配置
- 为Prometheus提供指标采集接口
- 提供友好的Web界面展示Redis节点状态
- 多线程并行收集Redis节点指标
- 支持监控KVRocks和Redis多种引擎

## 截图

### 首页

![首页](https://github.com/luger1990/kvdb-sentinel-exporter/raw/main/docs/images/index.png)

### 详情页

![详情页](https://github.com/luger1990/kvdb-sentinel-exporter/raw/main/docs/images/info.png)

### Grafana指标展示页

![Grafana指标展示页](https://github.com/luger1990/kvdb-sentinel-exporter/raw/main/docs/images/grafana.png)

## 安装

### 依赖项

- Python 3.9+
- Redis 5.0+
- Flask 2.3+
- Prometheus Client

### 从源码安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/kvdb-sentinel-exporter.git
cd kvdb-sentinel-exporter

# 安装依赖
pip install -r requirements.txt

# 配置
cp .env.example .env
cp config.yaml config.local.yaml  # 根据需要修改配置
```

### 使用Docker

```bash
# 使用预构建镜像
docker pull luger1990/kvdb-sentinel-exporter

# 或者从Dockerfile构建
docker build -t kvdb-sentinel-exporter .

# 运行容器
docker run -dit \
  -p 16379:16379 \
  --name=kvdb-sentinel-exporter \
  -v $(pwd)/config.yaml:/app/config.yaml \
  luger1990/kvdb-sentinel-exporter
  
# Docker支持的环境变量
docker run -dit \
  -p 16379:16379 \
  --name=kvdb-sentinel-exporter \
  -e DEBUG=true \
  -e HOST=127.0.0.1 \
  -e PORT=6379 \
  -e CONFIG_PATH=/app/config/config.yaml \
  -v $(pwd)/config.yaml:/app/config.yaml \
  luger1990/kvdb-sentinel-exporter

# 推荐使用Docker Host模式运行
docker run -dit \
  --net=host \
  --name=kvdb-sentinel-exporter \
  -e DEBUG=false \
  -v $(pwd)/config.yaml:/app/config.yaml \
  luger1990/kvdb-sentinel-exporter
```




## 配置

配置文件采用YAML格式，默认路径为`config.yaml`。您也可以通过环境变量`CONFIG_PATH`自定义配置文件路径。

### 配置示例

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

### 环境变量

配置可以通过`.env`文件或环境变量设置：

- `DEBUG`: 是否启用调试模式（默认: false）
- `HOST`: 监听主机地址（默认: 0.0.0.0）
- `PORT`: 监听端口（默认: 16379）
- `CONFIG_PATH`: 配置文件路径（默认: config.yaml）

## 使用

### 启动服务

```bash
# 直接运行
python run.py

# 指定配置文件
python run.py /path/to/config.yaml

# 通过环境变量指定配置
CONFIG_PATH=/path/to/config.yaml python run.py
```

### 访问Web界面

访问 `http://localhost:16379/` 查看哨兵组列表

访问 `http://localhost:16379/<sentinel_name>/info` 查看特定哨兵组的Redis节点状态

### Prometheus指标

Prometheus指标接口：`http://localhost:16379/<sentinel_name>/metrics`

主要指标包括：

- `kvdb_up`: Redis实例是否在线
- `kvdb_role`: Redis节点角色
- `kvdb_memory_used_bytes`: Redis已使用内存
- `kvdb_connected_clients`: 客户端连接数
- `kvdb_commands_processed_total`: 处理的命令总数
- `kvdb_instantaneous_ops_per_sec`: 每秒操作数
- `kvdb_engine_type`: 引擎类型(Redis/KVRocks)

## Prometheus配置示例

```yaml
scrape_configs:
  - job_name: 'redis_sentinel'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:16379']
    metrics_path: '/nct-redis-sentinel/metrics'
```

## 开发模式与热重载功能

为了提高开发效率，本项目支持热重载功能，使您在修改代码或模板后无需手动重启服务器。

### 设置开发环境

1. 安装开发依赖
   ```bash
   pip install -r requirements.txt
   ```

2. 创建开发环境配置文件
   ```bash
   cp .env.example .env
   ```

3. 编辑`.env`文件，确保启用调试模式
   ```
   DEBUG=true
   ```

4. 启动服务器
   ```bash
   python run.py
   ```

### 热重载功能

当`DEBUG=true`时，应用将自动启用以下功能：

1. **自动重载**：修改Python文件、HTML模板、JavaScript或CSS文件后，应用会自动重新加载
2. **不缓存静态资源**：浏览器总是获取最新的静态资源版本
3. **调试工具栏**：在Web界面中显示调试工具栏，提供请求、路由和配置信息

监控的文件扩展名包括：
- `.py`（Python源文件）
- `.html`（HTML模板）
- `.js`（JavaScript文件）
- `.css`（CSS样式表）
- `.yaml`和`.yml`（配置文件）

## 许可证

[MIT](https://github.com/luger1990/kvdb-sentinel-exporter/blob/main/LICENSE)  