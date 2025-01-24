from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields
import asyncio
import logging
import sys
import os

# Add parent directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from errors import InvalidURLError, VideoNotFoundError, DownloadError, APIError
from yt import YouTubeDownloader

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
api = Api(app, 
    version='1.0',
    title='Video Downloader API',
    description='Video Downloader API for multiple platforms',
    doc='/docs'
)

ns = api.namespace('api', description='Video operations')

# API Models
url_model = api.model('URL', {
    'url': fields.String(required=True, description='Video URL')
})

def require_api_key(f):
    def wrapper(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')
        if not Config.API_KEY or api_key == Config.API_KEY:
            return f(*args, **kwargs)
        return {"message": "Invalid API key"}, 401
    return wrapper

# Error handlers
@app.errorhandler(APIError)
def handle_api_error(error):
    return error.to_dict(), error.status_code

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
    @ns.doc('下载视频',
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
        """下载视频"""
        try:
            data = request.get_json()
            if not data or 'url' not in data:
                raise InvalidURLError("URL is required")

            downloader = YouTubeDownloader()
            result = asyncio.run(downloader.get_download_url(data['url']))
            logger.info(f"Successfully processed URL: {data['url']}")
            return result
        except ValueError as e:
            raise InvalidURLError()
        except Exception as e:
            logger.error(f"Error processing URL: {data['url']}", exc_info=True)
            raise DownloadError()

# For local development
if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT) 