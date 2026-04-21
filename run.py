#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import sys
from app import create_app
from app.config import Config
from dotenv import load_dotenv

# 加载.env文件中的环境变量（如果存在）
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def load_runtime_config():
    """加载运行配置，供直接运行和Gunicorn导入时共用。"""
    try:
        config_path = os.environ.get('CONFIG_PATH', 'config.yaml')

        if len(sys.argv) > 1 and sys.argv[0].endswith('run.py'):
            config_path = sys.argv[1]

        Config.load_config(config_path)

        sentinel_names = Config.get_all_sentinel_names()
        if sentinel_names:
            logging.info(f"已配置的哨兵组: {', '.join(sentinel_names)}")
        else:
            logging.warning("未找到任何哨兵组配置")
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        raise


load_runtime_config()

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    
    # 运行应用
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 16379))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logging.info(f"启动KVDB Sentinel Exporter服务，监听于 {host}:{port}，调试模式: {debug}")
    
    app.run(host=host, port=port, debug=debug)
