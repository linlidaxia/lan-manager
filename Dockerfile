# LAN Device Manager - Dockerfile
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    iputils-ping \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app.py .
COPY templates/ ./templates/

# 创建数据目录
RUN mkdir -p /data

# 暴露端口
EXPOSE 5000

# 启动应用
CMD ["python", "app.py"]