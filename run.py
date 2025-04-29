#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import datetime
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

# 创建应用实例
app = create_app()

# 添加模板上下文处理器
@app.context_processor
def inject_now():
    return {'current_year': datetime.datetime.now().year}

if __name__ == '__main__':
    # 尝试加载配置
    try:
        # 获取配置文件路径，优先使用环境变量
        config_path = os.environ.get('CONFIG_PATH', 'config.yaml')
        
        # 如果提供了命令行参数，则用第一个参数作为配置文件路径
        if len(sys.argv) > 1:
            config_path = sys.argv[1]
            
        Config.load_config(config_path)
        
        # 检查是否有任何哨兵组
        sentinel_names = Config.get_all_sentinel_names()
        if sentinel_names:
            logging.info(f"已配置的哨兵组: {', '.join(sentinel_names)}")
        else:
            logging.warning("未找到任何哨兵组配置")
    except Exception as e:
        logging.error(f"加载配置文件失败: {str(e)}")
        sys.exit(1)  # 如果配置加载失败，退出程序
    
    # 运行应用
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 16379))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logging.info(f"启动KVDB Sentinel Exporter服务，监听于 {host}:{port}，调试模式: {debug}")
    
    app.run(host, port, debug)