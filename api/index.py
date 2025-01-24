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
from twitter import TwitterParser
from tiktok import TiktokDownloader
from qishui import QishuiParser
from easy_downloader import EasyDownloaderAPI

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

async def run_async(coro):
    """运行异步代码的辅助函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return await coro
    finally:
        loop.close()

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

class YouTubeDownload(Resource):
    @require_api_key
    def post(self):
        """下载YouTube视频"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            downloader = YouTubeDownloader()
            result = asyncio.run(downloader.get_download_url(url))
            logger.info(f"Successfully processed YouTube URL: {url}")
            return result
        except ValueError as e:
            raise InvalidURLError()
        except Exception as e:
            logger.error(f"Error processing YouTube URL: {url}", exc_info=True)
            raise DownloadError()

class TwitterDownload(Resource):
    @require_api_key
    def post(self):
        """下载Twitter视频"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            parser = TwitterParser()
            result = asyncio.run(parser.get_download_url(url))
            logger.info(f"Successfully processed Twitter URL: {url}")
            return result
        except Exception as e:
            logger.error(f"Error processing Twitter URL: {url}", exc_info=True)
            raise DownloadError()

class TiktokDownload(Resource):
    @require_api_key
    def post(self):
        """下载TikTok视频"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            downloader = TiktokDownloader()
            result = asyncio.run(downloader.get_download_url(url))
            logger.info(f"Successfully processed TikTok URL: {url}")
            return result
        except Exception as e:
            logger.error(f"Error processing TikTok URL: {url}", exc_info=True)
            raise DownloadError()

class QishuiDownload(Resource):
    @require_api_key
    def post(self):
        """下载汽水音乐"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            parser = QishuiParser()
            result = asyncio.run(parser.get_download_url(url))
            logger.info(f"Successfully processed Qishui URL: {url}")
            return result
        except Exception as e:
            logger.error(f"Error processing Qishui URL: {url}", exc_info=True)
            raise DownloadError()

class UniversalDownload(Resource):
    @require_api_key
    def post(self):
        """通用视频下载"""
        try:
            args = url_parser.parse_args()
            url = args['url']

            downloader = EasyDownloaderAPI()
            result = asyncio.run(downloader.get_download_links(url))
            logger.info(f"Successfully processed URL: {url}")
            return result
        except Exception as e:
            logger.error(f"Error processing URL: {url}", exc_info=True)
            raise DownloadError()

# 注册路由
api.add_resource(Root, '/api/')
api.add_resource(Health, '/api/-/health')
api.add_resource(YouTubeDownload, '/api/youtube/download')
api.add_resource(TwitterDownload, '/api/twitter/download')
api.add_resource(TiktokDownload, '/api/tiktok/download')
api.add_resource(QishuiDownload, '/api/qishui/download')
api.add_resource(UniversalDownload, '/api/universal/download')

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
            "/api/youtube/download": {
                "post": {
                    "summary": "下载YouTube视频",
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
            },
            "/api/twitter/download": {
                "post": {
                    "summary": "下载Twitter视频",
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
            },
            "/api/tiktok/download": {
                "post": {
                    "summary": "下载TikTok视频",
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
            },
            "/api/qishui/download": {
                "post": {
                    "summary": "下载汽水音乐",
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
            },
            "/api/universal/download": {
                "post": {
                    "summary": "通用视频下载",
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