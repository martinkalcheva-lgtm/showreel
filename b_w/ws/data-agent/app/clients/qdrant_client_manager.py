import asyncio
import random
from typing import Optional
from qdrant_client import AsyncQdrantClient, models
from app.conf.app_config import QdrantConfig, app_config


class QdrantClientManager:
    """Qdrant向量数据库异步客户端管理器：封装客户端的初始化、关闭逻辑"""

    def __init__(self, qdrant_config: QdrantConfig):
        """
        初始化Qdrant客户端管理器
        """
        # 保存Qdrant连接配置
        self.qdrant_config = qdrant_config
        # 异步Qdrant客户端对象,初始为None
        self.client: Optional[AsyncQdrantClient] = None

    def _get_url(self):
        """拼接Qdrant连接的url"""
        return f"http://{self.qdrant_config.host}:{self.qdrant_config.port}"

    def init(self):
        """初始化异步Qdrant客户端(创建客户端实例）"""
        self.client = AsyncQdrantClient(self._get_url())

    async def close(self):
        """异步关闭Qdrant客户端，释放连接资源"""
        await self.client.close()


# 实例化Qdrant客户端（传入配置）
qdrant_client_manager = QdrantClientManager(app_config.qdrant)

if __name__ == "__main__":
    # 初始化Qdrant异步客户端
    qdrant_client_manager.init()


    async def test():
        # 获取初始化后的客户端
        client = qdrant_client_manager.client
        # 健壮性
        if not await client.collection_exists("my_collection"):
            await client.create_collection(
                collection_name="my_collection",
                vectors_config=models.VectorParams(size=10, distance=models.Distance.COSINE),
            )

        # 2. 批量插入100个10维随机向量到集合中
        await client.upsert(
            collection_name="my_collection",
            points=[
                models.PointStruct(
                    id=i,
                    vector=[random.random() for _ in range(10)]
                )
                for i in range(100)
            ],
        )

        # 3. 向量相似度检索：查找最相似的10个向量
        res = await client.query_points(
            collection_name="my_collection",  # 检索的集合名称
            query=[random.random() for _ in range(10)],
            limit=10,
            score_threshold=0.5
        )
        # 打印检索结果中的向量点信息（包含ID、向量、得分等）
        print(res.points)

        # 运行异步测试函数（asyncio.run是执行异步函数的标准方式）


    asyncio.run(test())
