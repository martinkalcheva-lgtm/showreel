# BOSS智库 knowledge_base —— 应用镜像
# 要点：
#   1) 依赖用 uv 按 uv.lock 精确安装，torch 走 CPU 源（无 GPU 环境）
#   2) 不 COPY .venv / .git / test（见 .dockerignore）
#   3) 容器内配置由挂载的 .env.docker 覆盖为 /app/.env
#   4) 模型不进镜像，运行时挂载到 /models/bge-m3

# 基础镜像走华为云 SWR 预同步源（docker.io 原址被墙限速，上次构建即死于此）
FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.11-slim

# 国内加速：用清华 PyPI 镜像装 uv（基础镜像自带 pip）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple uv==0.12.19 \
    && uv --version

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=180 \
    UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
    PYTHONPATH=/app

WORKDIR /app

# 第一层：只装依赖，利用 Docker 层缓存（改源码不必重装依赖）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 第二层：拷源码
COPY . .

# venv 可执行文件优先
ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000 8001

# 默认起导入服务；compose 里用 command 覆盖成查询服务
CMD ["python", "-m", "uvicorn", "web.api.import_service:app", "--host", "0.0.0.0", "--port", "8000"]
