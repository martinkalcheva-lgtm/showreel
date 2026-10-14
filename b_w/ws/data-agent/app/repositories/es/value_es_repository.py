#app\repositories\es\value_es_repository.py
from elasticsearch import AsyncElasticsearch

from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs


class ValueEsRepository:

    es_index_name="data-agent-values"
    es_index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {"type": "text", "analyzer": "ik_max_word", "search_analyzer": "ik_smart"},
            "type": {"type": "keyword"},
            "column_id": {"type": "keyword"},
            "column_name": {"type": "keyword"},
            "table_id": {"type": "keyword"},
            "table_name": {"type": "keyword"},
        }
    }

    def __init__(self,client:AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        """
        确保字段取值存储集合存在

        :return:
        """
        # 判断指定索引是否存在
        if not await self.client.indices.exists(index=self.es_index_name):
            # 不存在，则创建
            await self.client.indices.create(
                index=self.es_index_name,
                mappings=self.es_index_mappings
            )

    async def upsert_values(self, value_infos: list[ValueInfoEs], batch_size: int = 100):
        """
        批量保存字段取值到ES（存在则更新，不存在则创建）

        :param value_infos: 字段取值信息列表
        :param batch_size: 每批次处理的数据量
        :return:
        """
        # 空列表直接返回
        if not value_infos:
            return

        # 分批次处理
        for i in range(0, len(value_infos), batch_size):
            # 获取当前批次的值数据
            batch = value_infos[i:i + batch_size]
            # 构建bulk操作列表（action和document交替）
            operations = []
            for value_info in batch:
                # 构建index操作，指定_id实现upsert（存在则覆盖，不存在则创建）
                operations.append({"index": {"_index": self.es_index_name, "_id": value_info["id"]}})
                # 文档内容
                operations.append(dict(value_info))
            # 执行批量写入
            response = await self.client.bulk(operations=operations)
            # 检查是否有写入失败的文档
            if response["errors"]:
                logger.error(f"ES批量写入存在失败项: {response}")

    async def search(self, keyword:str,threshold:float=0.6,limit:int=5 )->list[ValueInfoEs]:
        """
        根据关键字keyword 在es中全文检索字段值数据
        :param keyword:
        :param threshold:
        :param limit:
        :return: list[ValueInfoES]
        """
        # 1.请求es的查询接口进行match查询
        result =await self.client.search(
            index=self.es_index_name,
            query={
                    "match": {
                        "value": keyword
                    }
                },
            min_score=threshold,
            size=limit,
        )
        # 2.解析查询结果
        return [hit['_source'] for hit in result["hits"]["hits"]]