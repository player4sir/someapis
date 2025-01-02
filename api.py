from dotenv import load_dotenv
load_dotenv()  # 添加在其他import之前

from fastapi import FastAPI, HTTPException, Security, Depends
from pydantic import BaseModel, Field
from typing import Optional, Any
from douyin import DouYinParser
from twitter import TwitterParser       
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
import os

app = FastAPI(
    title="社交媒体视频解析API",
    description="解析抖音和推特视频链接，获取无水印视频下载地址",
    version="1.0.0"
)

# 定义响应模型
class APIResponse(BaseModel):
    status: str = Field(..., description="响应状态: success 或 error")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")

# 定义请求模型
class VideoRequest(BaseModel):
    text: str = Field(..., description="包含视频链接的文本")

# 初始化解析器
douyin_parser = DouYinParser()
twitter_parser = TwitterParser()

# API Key配置
API_KEY = os.getenv("API_KEY", "your-default-api-key")  # 从环境变量获取API_KEY
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not api_key_header or api_key_header != API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API key"
        )
    return api_key_header

@app.post("/douyin/parse", summary="解析单个抖音视频", response_model=APIResponse)
async def parse_video(request: VideoRequest, api_key: str = Depends(get_api_key)):
    """
    解析单个抖音视频链接
    
    - **text**: 包含抖音视频链接的文本
    
    返回视频的详细信息，包括无水印下载地址
    """
    try:
        video_url = douyin_parser.extract_video_url(request.text)
        result = await douyin_parser.get_video_info_async(video_url)
        
        if result['status'] == 'error':
            return APIResponse(
                status="error",
                message=result['message'],
                data=None
            )
            
        return APIResponse(
            status="success",
            message="Video parsed successfully",
            data=result['data']
        )
        
    except ValueError as e:
        return APIResponse(
            status="error",
            message=str(e),
            data=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/twitter/parse", summary="解析单个推特视频", response_model=APIResponse)
async def parse_twitter_video(request: VideoRequest, api_key: str = Depends(get_api_key)):
    """
    解析单个推特视频链接
    
    - **text**: 包含推特视频链接的文本
    
    返回视频的详细信息，包括无水印下载地址
    """
    try:
        video_url = twitter_parser.extract_video_url(request.text)
        result = await twitter_parser.get_video_info_async(video_url)
        
        if result['status'] == 'error':
            return APIResponse(
                status="error",
                message=result['message'],
                data=None
            )
            
        return APIResponse(
            status="success",
            message="Video parsed successfully",
            data=result['data']
        )
        
    except ValueError as e:
        return APIResponse(
            status="error",
            message=str(e),
            data=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content=APIResponse(
            status="error",
            message="Invalid request data",
            data={"details": str(exc)}
        ).model_dump()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            status="error",
            message="Internal server error",
            data={"details": str(exc)}
        ).model_dump()
    ) 