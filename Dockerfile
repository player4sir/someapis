# 使用官方 Python 基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PORT=5000 \
    DEBUG=False

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装依赖，使用清华源
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 创建日志目录
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 5000

# 设置健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/-/health || exit 1

# 启动命令
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "main:app"] 