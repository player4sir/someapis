import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app

# Vercel 需要的处理函数
def handler(request):
    return app

# 为了本地测试
if __name__ == "__main__":
    app.run() 