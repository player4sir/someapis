from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

class Config:
    # API配置
    API_KEY = os.getenv('API_KEY','123456')
    # Vercel 环境使用 VERCEL_URL
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    IS_VERCEL = os.getenv('VERCEL', '').lower() == 'true'

    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
    
    # Vercel 环境配置
    if IS_VERCEL:
        BASE_URL = f"https://{os.getenv('VERCEL_URL', '')}"
    else:
        BASE_URL = os.getenv('BASE_URL', f"http://localhost:{PORT}") 