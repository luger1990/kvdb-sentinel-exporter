from flask import Flask, request, g
from flask_bootstrap import Bootstrap
import time
import logging
from flask_debugtoolbar import DebugToolbarExtension

def create_app(config_override=None):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    Bootstrap(app)
    
    # 添加调试工具栏（仅在DEBUG模式下启用）
    app.config['SECRET_KEY'] = 'dev-key-for-debugging'  # 调试工具栏需要SECRET_KEY
    app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
    toolbar = DebugToolbarExtension(app)
    
    # 配置Jinja2模板自动重载
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # 允许传入配置覆盖
    if config_override:
        app.config.update(config_override)
    
    from .routes import bp
    app.register_blueprint(bp)
    
    # 添加请求时间记录中间件
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            elapsed_time = time.time() - g.start_time
            logging.info(f"{request.method} {request.path} - 状态码: {response.status_code} - 耗时: {elapsed_time:.4f}秒")
        
        # 设置不缓存响应的头信息（对于开发环境很有用）
        if app.debug:
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        
        return response
    
    return app 