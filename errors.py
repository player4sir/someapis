from flask import jsonify
from werkzeug.exceptions import HTTPException
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIError(Exception):
    """API错误的基类"""
    def __init__(self, message, status_code=400, error_code=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or status_code

    def to_dict(self):
        return {
            'success': False,
            'error': {
                'code': self.error_code,
                'message': self.message,
                'status': self.status_code
            }
        }

class InvalidURLError(APIError):
    """无效URL错误"""
    def __init__(self, message="Invalid URL format"):
        super().__init__(message=message, status_code=400, error_code=4001)

class VideoNotFoundError(APIError):
    """视频未找到错误"""
    def __init__(self, message="Video not found"):
        super().__init__(message=message, status_code=404, error_code=4041)

class DownloadError(APIError):
    """下载错误"""
    def __init__(self, message="Failed to download video"):
        super().__init__(message=message, status_code=500, error_code=5001)

def handle_api_error(app):
    """注册错误处理器"""
    
    @app.errorhandler(APIError)
    def handle_custom_error(error):
        # 认证错误使用 INFO 级别，其他错误使用 ERROR 级别
        if error.status_code == 401:
            logger.info(f"Authentication error: {error.message}")
        else:
            logger.error(f"API Error: {error.message}")
            
        return error.to_dict(), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        # 4xx错误使用 INFO 级别，5xx错误使用 ERROR 级别
        if error.code >= 500:
            logger.error(f"Server error: {error}")
        else:
            logger.info(f"Client error: {error}")
            
        return {
            'success': False,
            'error': {
                'code': error.code,
                'message': error.description,
                'status': error.code
            }
        }, error.code

    @app.errorhandler(Exception)
    def handle_generic_error(error):
        logger.error(f"Unexpected error: {str(error)}")
        return {
            'success': False,
            'error': {
                'code': 500,
                'message': str(error),
                'status': 500
            }
        }, 500 