from typing import Union
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncSession, async_sessionmaker

from app.conf.app_config import DBConfig,app_config

class MysqlClientManager:
    # 初始值
    def __init__(self,db_config: DBConfig):
        self.db_config = db_config
        self.engine:Union[AsyncEngine,None] = None
        self.session_factory=None

    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"

    # 自己的初始值
    def init(self):
        # 创建异步引擎
        self.engine = create_async_engine(
            # 指定数据地址
            self._get_url(),
            # 设置连接池最大空闲连接数
            pool_size = 10,
            # 检测是否是死连接，自动替换新连接，避免业务错误
            pool_pre_ping = True
        )

        # 会话工厂
        self.session_factory = async_sessionmaker(
            # 绑定引擎
            bind = self.engine,
            # 自动刷新
            autoflush=False,
            # commit () 提交事务之后，会话里面这个 ORM 对象直接过期，对象属性清空。
            # 你再去访问对象的属性（比如 user.name），ORM 会自动偷偷再发一次 SQL 去数据库查询拿最新数据。
            expire_on_commit= False,
        )

    # 关闭引擎
    async def close(self):
        await self.engine.dispose()

dw_mysql_client_manager =MysqlClientManager(app_config.db_dw)
meta_mysql_client_manager = MysqlClientManager(app_config.db_meta)

if __name__ == '__main__':
    # 初始化客户端（创建引擎和会话工厂）
    dw_mysql_client_manager.init()

    # 定义异步测试函数
    async def test():
        async with dw_mysql_client_manager.session_factory() as session:
            # 待执行的 SQL
            sql = "select *from fact_order limit 10"

            # 执行 SQL，返回 Result 对象
            result = await session.execute(text(sql))

            # 提取结果（三种方式，按需选一种）：
            # rows = result.mappings().fetchall()  # 字典结构：[{}, {}, {}]
            rows = result.scalars().fetchall()      # 只取每行第一列的值：[v1, v2, v3]
            # rows = result.fetchall()             # 元组结构（Row 对象）：[(), (), ()]

            print(type(rows))
            print(rows)

        # 释放连接池资源
        await dw_mysql_client_manager.close()

    # 运行异步函数
    asyncio.run(test())