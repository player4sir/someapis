from dotenv import load_dotenv
import os

# 加载.env文件（如果存在）
if os.path.exists('.env'):
    load_dotenv()

class Config:
    # API配置
    API_KEY = os.environ.get('API_KEY')
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

    # CORS配置
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*') 