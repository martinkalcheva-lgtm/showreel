# main.py

"""
启动1
"""
import uvicorn

from conf.config import settings

if __name__ == '__main__':
    uvicorn.run(
        app="api.app:app", # 启动 FastAPI 服务
        host=settings.app_host,
        port=settings.app_port
    )