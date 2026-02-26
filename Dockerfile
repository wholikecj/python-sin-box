FROM python:3.12-slim

WORKDIR /root

# 安装必要的工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    ca-certificates \
    openssl \
    procps \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 脚本
COPY app.py /root/app.py
RUN chmod +x /root/app.py

# 确保必要的目录存在
RUN mkdir -p /root/app /root/app-data/common /root/app-data/singbox

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DOCKER_CONTAINER=1

# 默认安装所有协议并保持运行
CMD ["python3", "/root/app.py", "install"]
