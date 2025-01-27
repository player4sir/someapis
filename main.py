from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, reqparse
from yt import YouTubeMP3Converter
from twitter import TwitterParser
from tiktok import TiktokDownloader
from easy_downloader import EasyDownloaderAPI
import asyncio
import platform
import os
from functools import wraps
from config import Config
from errors import handle_api_error, APIError, InvalidURLError, VideoNotFoundError, DownloadError
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
from logging.config import dictConfig
from werkzeug.exceptions import HTTPException
from qishui import QishuiParser

# 配置日志
dictConfig({
    'version': 1,
    'formatters': {
        'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'level': 'INFO'
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    },
    'loggers': {
        'werkzeug': {
            'level': 'ERROR',  # 只显示错误级别的werkzeug日志
            'handlers': ['console'],
            'propagate': False
        },
        '__main__': {
            'level': 'INFO',
            'handlers': ['console'],
            'propagate': False
        }
    }
})

logger = logging.getLogger(__name__)

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app)

# 禁用Flask默认的日志处理
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True

# 注册错误处理器
handle_api_error(app)

api = Api(app, 
    title='视频/音频下载 API',
    version='1.0.0',
    description='''
    支持多平台视频/音频下载:
    - YouTube 视频下载
    - Twitter 视频下载
    - TikTok 视频下载
    - 汽水音乐(抖音音乐)下载
    - 通用视频下载
    ''',
    doc='/docs',
    authorizations={
        'apikey': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-API-KEY',
            'description': '访问 API 需要的密钥'
        }
    },
    security='apikey',
    errors={
        'APIError': {
            'message': '服务器内部错误',
            'status': 500,
        },
        'InvalidURLError': {
            'message': '无效的 URL 格式',
            'status': 400,
        },
        'VideoNotFoundError': {
            'message': '视频/音频未找到',
            'status': 404,
        },
        'DownloadError': {
            'message': '下载失败',
            'status': 500,
        }
    }
)

# 添加全局错误处理
@api.errorhandler(Exception)
def handle_exception(error):
    if isinstance(error, APIError):
        return error.to_dict(), error.status_code
    
    logger.error(f"Unexpected error: {str(error)}")
    return {
        'success': False,
        'error': {
            'code': 500,
            'message': str(error),
            'status': 500
        }
    }, 500

@api.errorhandler(HTTPException)
def handle_http_exception(error):
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

# 定义装饰器
def require_api_key(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            logger.info("Request without API key")
            raise APIError("Authentication required", status_code=401, error_code=4011)
        if api_key != Config.API_KEY:
            logger.info("Request with invalid API key")
            raise APIError("Invalid authentication credentials", status_code=401, error_code=4012)
        return func(*args, **kwargs)
    return decorated

# 定义命名空间
ns = api.namespace('api', 
    description='下载器 API 接口',
    decorators=[require_api_key]
)

# 定义请求模型
url_model = api.model('URL', {
    'url': fields.String(required=True, 
        description='视频/音频链接，支持 YouTube、Twitter、TikTok、汽水音乐等平台',
        example='https://qishui.douyin.com/s/xxx')
})

# Enable CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', Config.CORS_ORIGINS)
    response.headers.add('Access-Control-Allow-Headers', '*')
    response.headers.add('Access-Control-Allow-Methods', '*')
    return response

@ns.route('/')
class Root(Resource):
    @ns.doc(security='apikey')
    @require_api_key
    def get(self):
        """首页"""
        return {"message": "Video Downloader API is running"}

@ns.route('/-/health')
class Health(Resource):
    def get(self):
        """健康检查"""
        return {"status": "ok"}

@ns.route('/download')
class Download(Resource):
    @ns.expect(url_model)
    @ns.doc('下载YouTube视频',
        security='apikey',
        responses={
            200: 'Success',
            400: 'Invalid URL',
            401: 'Authentication failed',
            404: 'Video not found',
            500: 'Server Error'
        })
    @require_api_key
    def post(self):
        """下载YouTube视频"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                raise InvalidURLError("URL is required")

            downloader = YouTubeMP3Converter()
            result = downloader.get_download_url(data['url'])
            
            if result['status'] == 'success':
                logger.info(f"Successfully processed YouTube URL: {data['url']}")
                return result
            else:
                raise DownloadError(result.get('message', 'Unknown error'))
                
        except ValueError as e:
            raise InvalidURLError(str(e))
        except Exception as e:
            logger.error(f"Error processing YouTube URL: {data['url']}", exc_info=True)
            raise DownloadError(str(e))

@ns.route('/twitter/download')
class TwitterDownload(Resource):
    @ns.expect(url_model)
    @ns.doc('下载Twitter视频',
        security='apikey',
        responses={
            200: 'Success',
            400: 'Invalid URL',
            401: 'Authentication failed',
            404: 'Video not found',
            500: 'Server Error'
        })
    @require_api_key
    def post(self):
        """下载Twitter视频"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                raise InvalidURLError("URL is required")

            parser = TwitterParser()
            result = asyncio.run(parser.get_video_info_async(data['url']))
            logger.info(f"Successfully processed Twitter URL: {data['url']}")
            return result
        except ValueError as e:
            raise InvalidURLError()
        except Exception as e:
            logger.error(f"Error processing Twitter URL: {data['url']}", exc_info=True)
            raise DownloadError()

@ns.route('/tiktok/download')
class TiktokDownload(Resource):
    @ns.expect(url_model)
    @ns.doc('下载TikTok视频',
        security='apikey',
        responses={
            200: 'Success',
            400: 'Invalid URL',
            401: 'Invalid or missing API key',
            500: 'Server Error'
        })
    @require_api_key
    def post(self):
        """下载TikTok视频"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                return {"error": "URL is required"}, 400

            downloader = TiktokDownloader()
            result = asyncio.run(downloader.get_download_links(data['url']))
            return result
        except ValueError as e:
            return {"error": str(e)}, 400
        except Exception as e:
            return {"error": str(e)}, 500

@ns.route('/easy/download')
class EasyDownload(Resource):
    @ns.expect(url_model)
    @ns.doc('通用视频下载',
        security='apikey',
        responses={
            200: 'Success',
            400: 'Invalid URL',
            401: 'Authentication failed',
            500: 'Server Error'
        })
    @require_api_key
    def post(self):
        """通用视频下载接口"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                raise InvalidURLError("URL is required")

            downloader = EasyDownloaderAPI()
            result = asyncio.run(downloader.get_download_links(data['url']))
            
            if result['status'] == 'error':
                raise DownloadError(result['message'])
                
            logger.info(f"Successfully processed URL: {data['url']}")
            return result
            
        except ValueError as e:
            raise InvalidURLError()
        except Exception as e:
            logger.error(f"Error processing URL: {data['url']}", exc_info=True)
            raise DownloadError()

@ns.route('/qishui/parse')
class QishuiParseAPI(Resource):
    @api.doc('parse_qishui',
        description='解析汽水音乐链接，获取音乐标题、作者、封面等信息',
        responses={
            200: '解析成功',
            400: '无效的汽水音乐链接',
            401: '未授权访问',
            404: '音乐未找到',
            500: '服务器错误'
        })
    @api.expect(url_model)
    def post(self):
        """
        解析汽水音乐链接
        
        支持的链接格式:
        * https://qishui.douyin.com/s/xxx
        * 分享文本中的链接
        """
        data = api.payload
        if not data or 'url' not in data:
            raise InvalidURLError("URL is required")
            
        url = data['url'].strip()

        try:
            if 'qishui.douyin.com' not in url:
                raise InvalidURLError("仅支持汽水音乐链接")
                
            async def process_qishui():
                async with QishuiParser() as parser:
                    qishui_url = parser.extract_qishui_url(url)
                    return await parser.parse(qishui_url)
            
            result = asyncio.run(process_qishui())
            return result

        except InvalidURLError as e:
            raise APIError(str(e), 400)
        except VideoNotFoundError as e:
            raise APIError(str(e), 404)
        except Exception as e:
            logger.error(f"解析失败: {str(e)}")
            raise APIError("解析失败", 500)

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=Config.PORT,
        debug=Config.DEBUG
    )
