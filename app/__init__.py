import logging
import os
import time
import datetime

from .config import Config

def create_app(config_override=None):
    from flask import Flask, g, request
    from flask_bootstrap import Bootstrap

    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    Bootstrap(app)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
    app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False

    # 允许传入配置覆盖
    if config_override:
        app.config.update(config_override)

    if app.debug or os.environ.get('DEBUG', 'false').lower() == 'true':
        try:
            from flask_debugtoolbar import DebugToolbarExtension
        except ModuleNotFoundError:
            logging.warning("DEBUG=true 但未安装 flask-debugtoolbar，跳过调试工具栏")
        else:
            DebugToolbarExtension(app)
        app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    from .routes import bp
    app.register_blueprint(bp)

    @app.context_processor
    def inject_template_globals():
        web_ui_config = Config.get_web_ui_config()
        return {
            'current_year': datetime.datetime.now().year,
            'analytics_enabled': web_ui_config.get('analytics_enabled', False),
        }
    
    # 添加请求时间记录中间件
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            elapsed_time = time.time() - g.start_time
            logging.info("%s %s - 状态码: %s - 耗时: %.4f秒", request.method, request.path, response.status_code, elapsed_time)
        
        # 设置不缓存响应的头信息（对于开发环境很有用）
        if app.debug:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    return app 
