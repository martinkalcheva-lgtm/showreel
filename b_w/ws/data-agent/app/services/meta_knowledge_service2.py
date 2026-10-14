import uuid
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf
from scripts.regsetup import description

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.es.value_info_es import ValueInfoEs
from app.repositories.es.value_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository: MetaMysqlRepository,
                 dw_mysql_repository: DwMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 value_es_repository:ValueEsRepository,
                 ):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client = embedding_client
        self.value_es_repository = value_es_repository


    async def build(self, config: Path):
        # 1. 加载配置文件
        ## 1.1 读取配置内容
        context = OmegaConf.load(config)
        ## 1.2 定义封装结构
        schema = OmegaConf.structured(MetaConfig)
        # 1.3 合并转化配置对象
        meta_config = OmegaConf.to_object(OmegaConf.merge(schema, context))
        print(meta_config) # yaml读完  并且 连接MySQL的连接 也有
        # 2.处理表信息 Python实例  meta_config 就是 存了5张表 元信息的对象
        if meta_config.tables: #
            # 2.1保存表信息到meta数据库  2.1 这一步   完成 （把所有的表的信息  和 所有的字段的信息  记录到 meta库中  ）
            column_infos: list[ColumnInfoMySQL] = await self._save_table_info_to_meta_db(meta_config)
            logger.info("保存表信息到meta数据库")

            # 2.2为字段信息构建向量索引
            await self._save_column_info_to_qdrant(column_infos)
            logger.info("为字段构建向量索引")

            # 2.3为字段值构建全文索引
            await self._save_value_info_to_es(meta_config, column_infos)
            logger.info("为字段取值建立全文索引")

    async def _save_value_info_to_es(self, meta_config: MetaConfig, column_infos: list[ColumnInfoMySQL]):

        # 确保存储的索引存在
        await self.value_es_repository.ensure_index()
        # 保存字段取值到es
        # 定义字段接收数据
        column2sync: dict[str, bool] = {}
        # 获取所有字段的索引情况
        for table in meta_config.tables:
            # 遍历所有列
            for column in table.columns:
                column2sync[f"{table.name}.{column.name}"] = column.sync

        # 定义列表收集所有值数据
        value_infos: list[ValueInfoEs] = []
        # 遍历所有字段列表
        for column_info in column_infos:
            # 根据字段id，获取索引结果
            sync = column2sync[column_info.id]
            # 判断当前字段是否需要建立索引
            if sync:
                # 根据字段查询字段所属取值
                value_list: list[str] = await self.dw_mysql_repository.get_column_values(column_info.table_id,
                                                                                         column_info.name, 10000)

                # 封装全文索引字段取值数据
                for value_info in value_list:
                    # 封装值对象
                    value_info_es = ValueInfoEs(
                        id=f"{column_info.id}.{value_info}",
                        value=value_info,
                        type=column_info.type,
                        column_id=column_info.id,
                        column_name=column_info.name,
                        table_id=column_info.table_id,
                        table_name=column_info.table_id
                    )
                    value_infos.append(value_info_es)
        # 保存取值数据到es
        await self.value_es_repository.upsert_values(value_infos)



    def _convert_column_info_from_mysql_to_qdrant(self, column_info:ColumnInfoMySQL)->ColumnInfoQdrant:
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            alias=column_info.alias,
            table_id=column_info.table_id,
            description=column_info.description
        )

    async def _save_column_info_to_qdrant(self, column_infos: list[ColumnInfoMySQL]):
        # 2.2.1 确保存储字段的向量集合存在
        await self.column_qdrant_repository.ensure_collection()
        # 2.2.2 构建向量数据，存储qdrant数据库
        # 定义列表收集封装数据
        points: list[dict] = []
        # 遍历存储所有字段的列表
        for column_info in column_infos:

            # name
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.name,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
            })

            # description
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": column_info.description,
                "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
            })
            # alias
            for alia in column_info.alias:
                points.append({
                    "id": uuid.uuid4(),
                    "embedding_text": alia,
                    "payload": self._convert_column_info_from_mysql_to_qdrant(column_info)
                })

        # 获取所有向量文本
        embedding_texts: list[str] = [point["embedding_text"] for point in points]
        # 定义批次
        batch_size = 20
        # 定义向量列表
        embeddings: list[list[float]] = []
        # 遍历所有文本呢
        for i in range(0, len(embedding_texts), batch_size):
            # 获取批次文本
            batch_embedding_texts = embedding_texts[i:i + batch_size]
            # 转换向量 list[list[float]]
            batch_embedding = await self.embedding_client.aembed_documents(batch_embedding_texts)
            # 加入向量列表
            embeddings.extend(batch_embedding)

        # 获取所有id
        ids = [point["id"] for point in points]
        # 获取所有的payload
        payloads = [point["payload"] for point in points]

        # 保存字段数据到向量数据库
        await self.column_qdrant_repository.upsert_column_embeddings(ids, embeddings, payloads)

    async def _save_table_info_to_meta_db(self, meta_config: MetaConfig):
        # yaml 配置文件 我有5张表  元数据信息
        # 创建表信息封装列表
        table_infos: list[TableInfoMySQL] = []
        # 创建字段信息封装列表
        column_infos: list[ColumnInfoMySQL] = []
        # 遍历配置表信息，封装数据对象
        for table in meta_config.tables:
            # 封装表信息结构对象  TableInfoMySQL Python中模型类
            table_info_mysql = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description
            )
            # table_info_mysql 对象
            # table_infos 5张表 对象（数据）
            table_infos.append(table_info_mysql)

            # 查询表中所有字段的类型数据
            column_types: dict[str, str] = await self.dw_mysql_repository.get_column_types(table.name)

            # 遍历当前表中关联的字段列表
            for column in table.columns:
                # 根据表和字段查询字段取值
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(table.name, column.name)
                # 封装字段对象信息
                column_info_mysql = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name
                )
                column_infos.append(column_info_mysql)

        # #保存表信息到数据库
        # async with self.meta_mysql_repository.session.begin():
        #     await self.meta_mysql_repository.save_table_infos(table_infos)
        #     await self.meta_mysql_repository.save_column_infos(column_infos)
        return column_infos

