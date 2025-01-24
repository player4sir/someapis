from flask import Flask, request, jsonify
from flask_restful import Api, Resource, reqparse
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
api = Api(app)

# 请求参数解析
url_parser = reqparse.RequestParser()
url_parser.add_argument('url', type=str, required=True, help='Video URL is required')

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

class Root(Resource):
    @require_api_key
    def get(self):
        """首页"""
        return {"message": "Video Downloader API is running"}

class Health(Resource):
    def get(self):
        """健康检查"""
        return {"status": "ok"}

class Download(Resource):
    @require_api_key
    def post(self):
        """下载视频"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            downloader = YouTubeDownloader()
            result = asyncio.run(downloader.get_download_url(url))
            logger.info(f"Successfully processed URL: {url}")
            return result
        except ValueError as e:
            raise InvalidURLError()
        except Exception as e:
            logger.error(f"Error processing URL: {url}", exc_info=True)
            raise DownloadError()

# 注册路由
api.add_resource(Root, '/api/')
api.add_resource(Health, '/api/-/health')
api.add_resource(Download, '/api/download')

# 添加Swagger UI路由
@app.route('/docs')
def docs():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Video Downloader API Documentation</title>
        <meta charset="utf-8"/>
        <link rel="stylesheet" type="text/css" href="//unpkg.com/swagger-ui-dist@3/swagger-ui.css" />
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="//unpkg.com/swagger-ui-dist@3/swagger-ui-bundle.js"></script>
        <script>
            const ui = SwaggerUIBundle({
                url: "/api/swagger.json",
                dom_id: '#swagger-ui',
            })
        </script>
    </body>
    </html>
    """

@app.route('/api/swagger.json')
def swagger():
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Video Downloader API",
            "version": "1.0.0"
        },
        "paths": {
            "/api/": {
                "get": {
                    "summary": "首页",
                    "security": [{"apiKey": []}],
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            },
            "/api/-/health": {
                "get": {
                    "summary": "健康检查",
                    "responses": {
                        "200": {
                            "description": "Success"
                        }
                    }
                }
            },
            "/api/download": {
                "post": {
                    "summary": "下载视频",
                    "security": [{"apiKey": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "url": {
                                            "type": "string",
                                            "description": "Video URL"
                                        }
                                    },
                                    "required": ["url"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Success"
                        },
                        "400": {
                            "description": "Invalid URL"
                        },
                        "401": {
                            "description": "Authentication failed"
                        },
                        "404": {
                            "description": "Video not found"
                        },
                        "500": {
                            "description": "Server Error"
                        }
                    }
                }
            }
        },
        "components": {
            "securitySchemes": {
                "apiKey": {
                    "type": "apiKey",
                    "name": "X-API-KEY",
                    "in": "header"
                }
            }
        }
    }

# For local development
if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=Config.PORT) 