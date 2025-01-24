from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
from config import Config
from yt import YouTubeDownloader
from twitter import TwitterParser
from tiktok import TiktokDownloader
from easy_downloader import EasyDownloaderAPI
from qishui import QishuiParser
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='视频/音频下载 API',
    version='1.0.0',
    description='''
    支持多平台视频/音频下载:
    - YouTube 视频下载
    - Twitter 视频下载
    - TikTok 视频下载
    - 汽水音乐(抖音音乐)下载
    - 通用视频下载
    '''
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求模型
class URLInput(BaseModel):
    url: str

# API 密钥验证
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    if x_api_key != Config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

@app.get("/api")
async def root():
    """首页"""
    return {"message": "Video Downloader API is running"}

@app.get("/api/-/health")
async def health():
    """健康检查"""
    return {"status": "ok"}

@app.post("/api/download")
async def download(url_input: URLInput, api_key: str = Depends(verify_api_key)):
    """下载YouTube视频"""
    try:
        downloader = YouTubeDownloader()
        result = await downloader.get_download_url(url_input.url)
        logger.info(f"Successfully processed YouTube URL: {url_input.url}")
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as e:
        logger.error(f"Error processing YouTube URL: {url_input.url}", exc_info=True)
        raise HTTPException(status_code=500, detail="Download failed")

@app.post("/api/twitter/download")
async def twitter_download(url_input: URLInput, api_key: str = Depends(verify_api_key)):
    """下载Twitter视频"""
    try:
        parser = TwitterParser()
        result = await parser.get_video_info_async(url_input.url)
        logger.info(f"Successfully processed Twitter URL: {url_input.url}")
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as e:
        logger.error(f"Error processing Twitter URL: {url_input.url}", exc_info=True)
        raise HTTPException(status_code=500, detail="Download failed")

@app.post("/api/tiktok/download")
async def tiktok_download(url_input: URLInput, api_key: str = Depends(verify_api_key)):
    """下载TikTok视频"""
    try:
        downloader = TiktokDownloader()
        result = await downloader.get_download_links(url_input.url)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/easy/download")
async def easy_download(url_input: URLInput, api_key: str = Depends(verify_api_key)):
    """通用视频下载"""
    try:
        downloader = EasyDownloaderAPI()
        result = await downloader.get_download_links(url_input.url)
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result['message'])
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/qishui/parse")
async def qishui_parse(url_input: URLInput, api_key: str = Depends(verify_api_key)):
    """解析汽水音乐"""
    try:
        async with QishuiParser() as parser:
            qishui_url = parser.extract_qishui_url(url_input.url)
            result = await parser.parse(qishui_url)
            return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 