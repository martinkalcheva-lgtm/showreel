import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoStata, MetricInfoStata, ColumnInfoState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


# ===========================================================================
# 核心合并节点：将三路召回（列、指标、取值）的结果合并为统一的表/指标结构
# ===========================================================================
async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """
    合并三路召回结果，输出统一的表信息列表 + 指标信息列表。

    处理流程：
      1. 指标 → 列：指标关联的字段如果不在召回列中，从 MySQL 补查
      2. 取值 → 列：取值对应的字段如果不在召回列中，从 MySQL 补查；
         同时将取值写入对应列的 examples 列表
      3. 列 → 表：按 table_id 分组，将列归类到各自所属的表
      4. 补主外键：每张表显式补充主键 / 外键字段
      5. 列转换：ColumnInfoQdrant → ColumnInfoState
      6. 指标转换：MetricInfoQdrant → MetricInfoStata
    """
    writer=runtime.stream_writer
    writer({"stage":"合并召回信息"})
    try:
        # ---- 从 state 中获取三路召回结果 ----
        retrieved_columns: list[ColumnInfoQdrant] = state["retrieved_columns"]
        retrieved_values: list[ValueInfoEs] = state["retrieved_values"]
        retrieved_metrics: list[MetricInfoQdrant] = state["retrieved_metrics"]

        # 获取 MySQL 元数据查询对象
        meta_mysql_repository = runtime.context["meta_mysql_repository"]

        # ---- 将召回的列列表转为 dict，以列 id 为 key，方便后续去重与查找 ----
        retrieved_columns_map:dict[str, ColumnInfoQdrant] = {
            retrieved_column['id'] : retrieved_column for retrieved_column in retrieved_columns
        }

        # ================================================================
        # 处理一：指标 → 列
        #   遍历每个指标关联的 relevant_columns，
        #   如果关联的列不在召回列字典中，就从 MySQL 查询并补充进来
        # ================================================================
        for retrieved_metric in retrieved_metrics:
            relevant_columns = retrieved_metric["relevant_columns"]
            for relevant_column_id in relevant_columns:
                if relevant_column_id not in retrieved_columns_map:
                    # 从 MySQL 查询列信息
                    column_info_mysql: ColumnInfoMySQL = await meta_mysql_repository.get_column_info_by_id(
                        relevant_column_id
                    )
                    # 转换为 Qdrant 格式并加入字典
                    retrieved_columns_map[relevant_column_id] = convert_column_info_from_mysql_to_qdrant(
                        column_info_mysql
                    )

        # ================================================================
        # 处理二：取值 → 列
        #   遍历每个取值，找到它所属的列；
        #   如果列不在召回列字典中，从 MySQL 补查；
        #   然后把取值写入对应列的 examples 列表（去重）
        # ================================================================
        for retrieved_value in retrieved_values:
            column_value = retrieved_value["value"]
            column_id = retrieved_value["column_id"]

            # 如果取值对应的列不存在，从 MySQL 查询补充
            if column_id not in retrieved_columns_map:
                column_info_mysql = await meta_mysql_repository.get_column_info_by_id(column_id)
                retrieved_columns_map[column_id] = convert_column_info_from_mysql_to_qdrant(
                    column_info_mysql
                )

            # 安全处理：确保 examples 是 list（防止 None）
            col = retrieved_columns_map[column_id]
            if col.get("examples") is None:
                col["examples"] = []

            # 将取值加入 examples（去重）
            if column_value not in col["examples"]:
                col["examples"].append(column_value)

        # ================================================================
        # 处理三：列 → 表分组
        #   按 table_id 将所有列归类，得到 dict[table_id, list[ColumnInfoQdrant]]
        # ================================================================
        table_to_column_map: dict[str, list[ColumnInfoQdrant]] = {}
        for column in retrieved_columns_map.values():
            table_id = column["table_id"]
            if table_id not in table_to_column_map:
                table_to_column_map[table_id] = []
            table_to_column_map[table_id].append(column)

        # ================================================================
        # 处理四：显式补充每张表的主外键字段
        #   查询每张表的主外键 → 判断是否已在列列表中 → 不在则补充
        # ================================================================
        for table_id in table_to_column_map:
            # 查询该表的主外键字段
            key_columns: list[ColumnInfoMySQL] = await meta_mysql_repository.get_key_columns_by_table_id(
                table_id
            )
            # 当前表已有的列 id 集合
            existing_column_ids = [col["id"] for col in table_to_column_map[table_id]]
            # 遍历主外键，补充缺失的
            for key_column in key_columns:
                if key_column.id not in existing_column_ids:
                    table_to_column_map[table_id].append(
                        convert_column_info_from_mysql_to_qdrant(key_column)
                    )

        # ================================================================
        # 处理五：转换为 TableInfoStata 列表
        #   table_id → 查表信息 → 列转换 → 组装 TableInfoStata
        # ================================================================
        table_infos: list[TableInfoStata] = []
        for table_id, columns in table_to_column_map.items():
            # 查询表元信息
            table: TableInfoMySQL = await meta_mysql_repository.get_table_info_by_id(table_id)
            # 列转换：ColumnInfoQdrant → ColumnInfoState
            converted_columns = [
                convert_column_info_from_qdrant_to_state(col) for col in columns
            ]
            # 组装表信息
            table_info: TableInfoStata = {
                "name": table.name,
                "role": table.role,
                "description": table.description,
                "columns": converted_columns,
            }
            table_infos.append(table_info)

        # ================================================================
        # 处理六：指标信息转换 MetricInfoQdrant → MetricInfoStata
        # ================================================================
        metric_infos: list[MetricInfoStata] = [
            convert_metric_info_from_qdrant_to_state(m) for m in retrieved_metrics
        ]

        logger.info(f"合并完成: {len(table_infos)} 张表, {len(metric_infos)} 个指标")
        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as e:
        logger.error(f"合并召回信息异常: {str(e)}")
        raise


# ===========================================================================
# 转换函数
# ===========================================================================

def convert_metric_info_from_qdrant_to_state(metric: MetricInfoQdrant) -> MetricInfoStata:
    """MetricInfoQdrant → MetricInfoStata"""
    return {
        "name": metric["name"],
        "description": metric["description"],
        "relevant_columns": metric["relevant_columns"],
        "alias": metric["alias"],
    }


def convert_column_info_from_qdrant_to_state(col: ColumnInfoQdrant) -> ColumnInfoState:
    """ColumnInfoQdrant → ColumnInfoState"""
    return {
        "name": col["name"],
        "type": col["type"],
        "role": col["role"],
        "examples": col["examples"],
        "description": col["description"],
        "alias": col["alias"],
    }


def convert_column_info_from_mysql_to_qdrant(col_mysql: ColumnInfoMySQL) -> ColumnInfoQdrant:
    """ColumnInfoMySQL → ColumnInfoQdrant

    MySQL 模型用属性访问（.name），Qdrant 模型是 TypedDict 用 dict 访问（["name"]）
    """
    return {
        "id": col_mysql.id,
        "name": col_mysql.name,
        "type": col_mysql.type,
        "role": col_mysql.role,
        "examples": col_mysql.examples if col_mysql.examples else [],
        "description": col_mysql.description,
        "alias": col_mysql.alias if col_mysql.alias else [],
        "table_id": col_mysql.table_id,
    }


# ===========================================================================
# 调试入口：用 mock 数据模拟完整的合并流程
# ===========================================================================
if __name__ == "__main__":

    # ------------------------------------------------------------------
    # 1. 构造 mock 数据
    #    模拟场景：用户查询「统计华北地区销售总额」
    #    三路召回分别返回了部分列、指标、取值，merge 负责补全和组装
    # ------------------------------------------------------------------

    # --- 1.1 召回的列（来自 Qdrant 向量库，是 TypedDict / dict） ---
    # 注意：向量召回只命中了 order_amount 和 region_name，
    #       没有命中 order_date（c7），后续 merge 会通过指标关联补查
    mock_retrieved_columns: list[ColumnInfoQdrant] = [
        {
            "id": "c1",
            "name": "order_amount",
            "type": "float",
            "role": "measure",
            "examples": [10.2, 40.5],
            "description": "订单金额",
            "alias": ["amount"],
            "table_id": "t1",  # 属于 fact_order 表
        },
        {
            "id": "c5",
            "name": "region_name",
            "type": "varchar(50)",
            "role": "dimension",
            "examples": [],
            "description": "地区名称",
            "alias": ["region"],
            "table_id": "t2",  # 属于 dim_region 表
        },
    ]

    # --- 1.2 召回的指标（来自 Qdrant 向量库） ---
    # 指标 sales_total 关联了 c1(order_amount) 和 c7(order_date)
    # c7 不在召回列中 → merge 需要从 MySQL 补查
    mock_retrieved_metrics: list[MetricInfoQdrant] = [
        {
            "id": "m1",
            "name": "sales_total",
            "description": "销售总额",
            "relevant_columns": ["c1", "c7"],  # c7 未被召回，需要补查
            "alias": ["total_sales"],
        },
    ]

    # --- 1.3 召回的取值（来自 ES 全文检索） ---
    # v1、v2 对应的列 c5 已在召回列中 → 直接写入 examples
    # v3 对应的列 c7 不在召回列中 → 需要从 MySQL 补查后写入 examples
    mock_retrieved_values: list[ValueInfoEs] = [
        {"id": "v1", "value": "华北", "column_id": "c5"},
        {"id": "v2", "value": "华南", "column_id": "c5"},
        {"id": "v3", "value": "2024-01", "column_id": "c7"},  # c7 未被召回
    ]

    # ------------------------------------------------------------------
    # 2. 构造 mock MySQL 元数据仓库
    #    模拟 meta_mysql_repository 的三个异步方法
    # ------------------------------------------------------------------

    # MySQL 列模型（用 SimpleNamespace 模拟，属性访问方式）
    mysql_columns = {
        # c7: 未被向量召回，但被指标和取值引用，merge 会来这里查
        "c7": SimpleNamespace(
            id="c7", name="order_date", type="date", role="dimension",
            examples=[], description="订单日期", alias=["date"], table_id="t1",
        ),
        # c3: fact_order 的主键（补主外键时会查到）
        "c3": SimpleNamespace(
            id="c3", name="order_id", type="varchar(32)", role="primary_key",
            examples=[], description="订单ID", alias=[], table_id="t1",
        ),
        # c2: fact_order 的外键（补主外键时会查到）
        "c2": SimpleNamespace(
            id="c2", name="region_id", type="varchar(20)", role="foreign_key",
            examples=[1, 2, 3], description="地区维度外键", alias=["region_code"], table_id="t1",
        ),
        # c4: dim_region 的主键（补主外键时会查到）
        "c4": SimpleNamespace(
            id="c4", name="region_id", type="varchar(20)", role="primary_key",
            examples=[1, 2, 3], description="地区ID", alias=[], table_id="t2",
        ),
    }

    # MySQL 表模型
    mysql_tables = {
        "t1": SimpleNamespace(name="fact_order", role="fact", description="订单事实表"),
        "t2": SimpleNamespace(name="dim_region", role="dimension", description="地区维度表"),
    }

    # 各表的主外键列 id 列表
    table_key_column_ids = {
        "t1": ["c3", "c2"],   # fact_order: order_id(PK), region_id(FK)
        "t2": ["c4"],          # dim_region: region_id(PK)
    }

    class MockMetaMysqlRepository:
        """模拟 MySQL 元数据查询仓库"""

        async def get_column_info_by_id(self, column_id: str) -> ColumnInfoMySQL:
            print(f"  [MySQL] 查询列信息: column_id={column_id}")
            col = mysql_columns.get(column_id)
            if col is None:
                raise ValueError(f"未找到列: {column_id}")
            return col

        async def get_key_columns_by_table_id(self, table_id: str) -> list[ColumnInfoMySQL]:
            print(f"  [MySQL] 查询表主外键: table_id={table_id}")
            ids = table_key_column_ids.get(table_id, [])
            return [mysql_columns[cid] for cid in ids]

        async def get_table_info_by_id(self, table_id: str) -> TableInfoMySQL:
            print(f"  [MySQL] 查询表信息: table_id={table_id}")
            return mysql_tables[table_id]

    # ------------------------------------------------------------------
    # 3. 构造 state 和 runtime
    # ------------------------------------------------------------------
    state: DataAgentState = {
        "query": "统计华北地区销售总额",
        "keywords": ["统计", "销售总额", "华北地区"],
        "retrieved_columns": mock_retrieved_columns,
        "retrieved_values": mock_retrieved_values,
        "retrieved_metrics": mock_retrieved_metrics,
    }

    runtime = MagicMock()
    runtime.stream_writer = lambda x: print(f"  [进度] {x}")
    runtime.context = {
        "meta_mysql_repository": MockMetaMysqlRepository(),
    }

    # ------------------------------------------------------------------
    # 4. 执行合并
    # ------------------------------------------------------------------
    async def main():
        print("=" * 70)
        print("开始执行 merge_retrieved_info")
        print("=" * 70)

        print("\n--- 输入数据 ---")
        print(f"召回列: {[c['name'] for c in mock_retrieved_columns]}")
        print(f"召回指标: {[m['name'] for m in mock_retrieved_metrics]}")
        print(f"召回取值: {[v['value'] for v in mock_retrieved_values]}")

        print("\n--- 执行合并 ---")
        result = await merge_retrieved_info(state, runtime)

        print("\n" + "=" * 70)
        print("合并结果")
        print("=" * 70)

        # 打印表信息
        table_infos = result["table_infos"]
        print(f"\n📊 共 {len(table_infos)} 张表:")
        for t in table_infos:
            print(f"\n  表名: {t['name']}")
            print(f"  角色: {t['role']}")
            print(f"  描述: {t['description']}")
            print(f"  字段 ({len(t['columns'])} 个):")
            for c in t["columns"]:
                examples_str = c["examples"] if c["examples"] else "[]"
                alias_str = c["alias"] if c["alias"] else "[]"
                print(f"    - {c['name']} ({c['type']}, {c['role']})")
                print(f"      描述: {c['description']}")
                print(f"      示例: {examples_str}")
                print(f"      别名: {alias_str}")

        # 打印指标信息
        metric_infos = result["metric_infos"]
        print(f"\n📐 共 {len(metric_infos)} 个指标:")
        for m in metric_infos:
            print(f"\n  指标名: {m['name']}")
            print(f"  描述: {m['description']}")
            print(f"  关联列: {m['relevant_columns']}")
            print(f"  别名: {m['alias']}")

        print("\n" + "=" * 70)
        print("✅ 合并完成")
        print("=" * 70)

    asyncio.run(main())
