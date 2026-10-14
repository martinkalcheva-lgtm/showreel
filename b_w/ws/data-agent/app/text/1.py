import uuid
from pathlib import Path

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from omegaconf import OmegaConf

from app.conf.meta_config import MetaConfig
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.repository.es.value_es_repository import ValueEsRepository
from app.repository.mysql.dw_mysql_repository import DWMysqlRepository
from app.repository.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repository.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repository.qdrant.metric_qdrant_repository import MetricQdrantRepository


class MetaKnowledgeService:
    def __init__(self,
                 meta_mysql_repository: MetaMysqlRepository,
                 dw_mysql_repository: DWMysqlRepository,
                 column_qdrant_repository: ColumnQdrantRepository,
                 embedding_client: HuggingFaceEndpointEmbeddings,
                 value_es_repository: ValueEsRepository,
                 metric_qdrant_repository: MetricQdrantRepository):
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository
        self.column_qdrant_repository = column_qdrant_repository
        self.embedding_client = embedding_client
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository

    async def build(self, config_file: Path):
        # 1.加载配置文件，构建配置对象
        # 根据文件路径加载配置文件内容
        context = OmegaConf.load(config_file)
        # 构建配置内容封装结构
        schema = OmegaConf.structured(MetaConfig)
        # 合并结构和内容后转换成对象
        meta_config: MetaConfig = OmegaConf.to_object(OmegaConf.merge(schema, context))
        logger.info("加载配置文件完成")
        # 判断配置中是否存在表的配置信息
        if meta_config.tables:
            # 2.处理表信息，
            # 2.1添加表信息到meta数据库
            column_infos: list[ColumnInfoMySQL] = await self._save_table_info_to_meta_db(meta_config)
            logger.info("保存表信息到meta数据库")
            # 2.2为列信息构建向量索引qdrant
            await self._save_column_info_to_qdrant(column_infos)
            logger.info("为列信息添加向量索引")
            # 2.3为列值信息构建全文索引
            await self._save_value_info_to_es(column_infos, meta_config)
            logger.info("为值信息添加全文索引")

        # 判断配置中是否存在指标的配置信息
        if meta_config.metrics:
            # 3.处理指标信息
            # 3.1 保存指标到meta数据库
            metric_infos: list[MetricInfoMySQL] = await self._save_metric_info_to_meta_db(meta_config)
            logger.info("保存指标信息到meta数据库")
            # 3.2为指标信息构建向量索引
            await self._save_metric_info_to_qdrant(metric_infos)
            logger.info("为指标信息添加向量索引")

    async def _save_table_info_to_meta_db(self, meta_config: MetaConfig) -> list[ColumnInfoMySQL]:
        # 定义列表收集表信息
        table_infos: list[TableInfoMySQL] = []
        # 定义列表收集列信息
        column_infos: list[ColumnInfoMySQL] = []
        for table in meta_config.tables:
            # 查询当前表列的类型
            column_types: dict[str, str] = await self.dw_mysql_repository.get_column_types(table.name)
            # 构建表信息对象
            table_info = TableInfoMySQL(
                id=table.name,
                name=table.name,
                role=table.role,
                description=table.description
            )
            table_infos.append(table_info)
            # 遍历当前表的列数据
            for column in table.columns:
                # 查询指定列的examples
                column_values: list[str] = await self.dw_mysql_repository.get_column_values(table.name, column.name)

                # 构建列对象信息
                column_info = ColumnInfoMySQL(
                    id=f"{table.name}.{column.name}",
                    name=column.name,
                    type=column_types[column.name],
                    role=column.role,
                    examples=column_values,
                    description=column.description,
                    alias=column.alias,
                    table_id=table.name

                )
                column_infos.append(column_info)

        # 2.1保存表信息到table_info
        async with self.meta_mysql_repository.session.begin():
            await self.meta_mysql_repository.save_table_infos(table_infos)
            # 2.2保存列信息到column_info
            await self.meta_mysql_repository.save_column_infos(column_infos)
        return column_infos

    def _convert_column_info_from_mysql_to_qdrant(self, column_info: ColumnInfoMySQL):
        return ColumnInfoQdrant(
            id=column_info.id,
            name=column_info.name,
            type=column_info.type,
            role=column_info.role,
            examples=column_info.examples,
            description=column_info.description,
            alias=column_info.alias,
            table_id=column_info.table_id
        )

    async def _save_column_info_to_qdrant(self, column_infos: list[ColumnInfoMySQL]):
        # 确保列信息存储向量数据库集合存在
        await self.column_qdrant_repository.ensure_collection()
        # 构建列数据的保存点
        points: list[dict] = []
        # 遍历列集合数据，获取需要向量存储的字段
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

        # 获取所有points中的向量文本
        embeddings_text = [point["embedding_text"] for point in points]
        # 定义向量列表，收集向量数据 list[list[fload]]
        embeddings = []
        # 批次进行向量转化
        batch_size = 20
        # 循环总的向量文本，获取批次
        for i in range(0, len(embeddings_text), batch_size):
            # 获取批次数据
            batch_embedding_texts = embeddings_text[i:i + batch_size]
            # 转换向量文本为向量数据
            batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
        # list[list[fload]]
        embeddings.extend(batch_embeddings)

    # 收集id列表
    ids = [point["id"] for point in points]
    # 收集payload列表
    payloads = [point["payload"] for point in points]
    # 保存向量数据到qdrant中
    await self.column_qdrant_repository.upsert_embedding(ids, embeddings, payloads)


async def _save_value_info_to_es(self, column_infos: list[ColumnInfoMySQL], meta_config: MetaConfig):
    # 确保值存储的索引存在
    await self.value_es_repository.ensure_index()
    # 定义字典{“表名.列名”:true}
    column2sync: dict[str, bool] = {}
    # 查询需要进行全文索引的列
    for table in meta_config.tables:
        # 循环当前表对应列
        for column in table.columns:
            column2sync[f"{table.name}.{column.name}"] = column.sync
    # 接收所有值对象，用于进行全文检索存储
    value_infos: list[ValueInfoEs] = []
    # 根据需要全文索引的列，查询对应的值列表
    for column_info in column_infos:
        # 获取当前列是否进行全文索引的结果
        sync = column2sync[column_info.id]
        # 判断结果
        if sync:
            # 根据列查询对应的值列表
            values: list[str] = await self.dw_mysql_repository.get_column_values(column_info.table_id,
                                                                                 column_info.name, 10000)
            # 构建值实体数据
            current_column_values = [ValueInfoEs(
                id=f"{column_info.id}.{value}",  # 表名.列表.值
                value=value,
                type=column_info.type,
                column_id=column_info.id,
                column_name=column_info.name,
                table_id=column_info.table_id,
                table_name=column_info.table_id

            ) for value in values]
            value_infos.extend(current_column_values)

    # 保存值数据到es
    await self.value_es_repository.upsert_values(value_infos)


async def _save_metric_info_to_meta_db(self, meta_config: MetaConfig):
    # 封装数据位MetricInfoMysql
    metric_infos: list[MetricInfoMySQL] = []
    column_metric_infos: list[ColumnMetricMySQL] = []
    # 遍历封装处理
    for metric in meta_config.metrics:
        metric_info = MetricInfoMySQL(
            id=metric.name,
            name=metric.name,
            description=metric.description,
            relevant_columns=metric.relevant_columns,
            alias=metric.alias
        )
        metric_infos.append(metric_info)
        # 处理列指标关联信息
        for relevant_column in metric.relevant_columns:
            relevant_column_info = ColumnMetricMySQL(
                column_id=relevant_column,
                metric_id=metric.name
            )
            column_metric_infos.append(relevant_column_info)
    async with self.meta_mysql_repository.session.begin():
        # 保存指标信息到metric_info
        await self.meta_mysql_repository.save_metric_infos(metric_infos)
        #  保存列指标信息到column_metric
        await self.meta_mysql_repository.save_column_metric_infos(column_metric_infos)
    return metric_infos


def _convert_metric_info_from_mysql_to_qdrant(self, metric_info: MetricInfoMySQL):
    return MetricInfoQdrant(
        id=metric_info.id,
        name=metric_info.name,
        description=metric_info.description,
        relevant_columns=metric_info.relevant_columns,
        alias=metric_info.alias
    )


async def _save_metric_info_to_qdrant(self, metric_infos: list[MetricInfoMySQL]):
    # 确保指标信息存储的集合存在
    await self.metric_qdrant_repository.ensure_collection()

    # 接收points数据
    points: list[dict] = []
    # 构建指标points数据结构
    for metric_info in metric_infos:
        # name
        points.append({
            "id": uuid.uuid4(),
            "embedding_text": metric_info.name,
            "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
        })
        # description
        points.append({
            "id": uuid.uuid4(),
            "embedding_text": metric_info.description,
            "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
        })
        # alias
        for alia in metric_info.alias:
            points.append({
                "id": uuid.uuid4(),
                "embedding_text": alia,
                "payload": self._convert_metric_info_from_mysql_to_qdrant(metric_info)
            })

    # 获取所有向量文本
    embedding_texts = [point["embedding_text"] for point in points]
    # 定义批次
    batch_size = 10
    # 定义接收向量数据列表
    embeddings = []
    # 循环获取批次
    for i in range(0, len(embedding_texts), batch_size):
        # 获取批次向量文本
        batch_embedding_texts = embedding_texts[i:i + batch_size]
        # 批次向量转换
        batch_embeddings = await self.embedding_client.aembed_documents(batch_embedding_texts)
        # 接收数据
        embeddings.extend(batch_embeddings)
    # 获取ids
    ids = [point["id"] for point in points]
    # 获取payloads
    payloads = [point["payload"] for point in points]
    # 保存指标信息到qdrant
    await self.metric_qdrant_repository.upsert_embeddings(ids, embeddings, payloads)