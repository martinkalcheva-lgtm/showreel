# itwwy/api/app.py

"""
定义fastapi实例

"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from infrastructure.http_client import init_http_client, close_http_client

from api.routers.chat_router import router
from infrastructure.database import init_db_engine, close_db_engine

# 装饰器 是 Python特有的语法 在不改变函数内部 代码的情况下 额外 增加新的功能
# 汽车 什么都不懂  拿去店里 额外 车顶 装个机关枪  封闭开放 （不主张 你去修改代码 但是 愿意让函数 有更多的功能）
@asynccontextmanager
async def lifespan(app: FastAPI):

    # 1. 应用启动
    print("启动服务器...")

    init_http_client() # 创建全局 httpx 客户端实例
    init_db_engine()  # 创建数据库连接池（只创建1次）

    # 2. 进入 yield
    yield  # ← FastAPI 开始接收请求

    await close_db_engine()
    await close_http_client()


    # 3. 应用关闭（Ctrl+C 或部署平台停止）
    await close_db_engine()  # ← 执行这里，关闭连接池
    print("服务器已关闭")

# 创建应用
app = FastAPI(description="电商小二智能客服应用", lifespan=lifespan)



# 路由分发
app.include_router(router)






