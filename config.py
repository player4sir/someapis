from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

class Config:
    # API配置
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

    # CORS配置
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*') 