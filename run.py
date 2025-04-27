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

def run_with_reloader(app, host, port, debug=False):
    """使用watchdog实现的自定义重载器运行应用"""
    if not debug:
        # 非调试模式直接运行
        app.run(host=host, port=port)
        return
    
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logging.warning("Watchdog未安装，将使用Flask自带的重载器。请使用pip install watchdog安装以获得更好的重载体验。")
        app.run(host=host, port=port, debug=True)
        return
    
    import threading
    import time
    import subprocess
    
    # 默认监控的文件扩展名
    watched_extensions = ['.py', '.html', '.js', '.css', '.yaml', '.yml']
    
    # 获取项目根目录
    app_dir = os.path.abspath(os.path.dirname(__file__))
    
    class AppReloader(FileSystemEventHandler):
        def __init__(self):
            self.process = None
            self.should_reload = False
            self.last_reload = 0
            self.start_process()
        
        def on_any_event(self, event):
            # 检查是否是我们关注的文件类型
            if event.is_directory:
                return
            file_ext = os.path.splitext(event.src_path)[1].lower()
            if file_ext not in watched_extensions:
                return
            
            # 添加防抖动逻辑，避免频繁重启
            current_time = time.time()
            if current_time - self.last_reload < 1:  # 至少间隔1秒
                return
            
            logging.info(f"检测到文件变化: {event.src_path}")
            self.should_reload = True
            self.last_reload = current_time
        
        def start_process(self):
            if self.process and self.process.poll() is None:
                self.process.terminate()
                self.process.wait()
            
            # 准备启动命令
            cmd = [sys.executable, __file__]
            if len(sys.argv) > 1:
                cmd.extend(sys.argv[1:])
            
            # 设置环境变量，确保子进程不会再次启动重载器
            env = os.environ.copy()
            env['FLASK_DEBUG'] = 'true'
            env['WATCHDOG_RELOADER_RUNNING'] = 'true'
            
            # 启动子进程
            self.process = subprocess.Popen(cmd, env=env)
            self.should_reload = False
        
        def watch_and_reload(self):
            while True:
                time.sleep(1)
                if self.should_reload:
                    try:
                        self.start_process()
                    except Exception as e:
                        logging.error(f"重启应用失败: {str(e)}")
    
    # 如果已经在重载器中运行，则直接启动应用
    if os.environ.get('WATCHDOG_RELOADER_RUNNING') == 'true':
        app.run(host=host, port=port, use_reloader=False)
        return
    
    # 启动文件监控
    logging.info("启动文件变更监控...")
    event_handler = AppReloader()
    observer = Observer()
    observer.schedule(event_handler, app_dir, recursive=True)
    observer.start()
    
    # 启动重载线程
    reload_thread = threading.Thread(target=event_handler.watch_and_reload)
    reload_thread.daemon = True
    reload_thread.start()
    
    try:
        # 保持主线程运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

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
    
    # 使用自定义重载器运行应用
    run_with_reloader(app, host, port, debug) 