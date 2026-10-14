import asyncio
import yaml
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoStata, ColumnInfoState
from app.core.log import logger
from app.prompts.prompt_loader import loder_prompt  # 修复: loder_prompt → loader_prompt


# ===========================================================================
# 过滤表信息节点：用 LLM 从合并后的表/字段中筛选出与用户查询相关的部分
# ===========================================================================
async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "过滤表"})
    try:
        # 获取用户查询
        query = state["query"]
        # 获取合并后的表数据
        table_infos: list[TableInfoStata] = state["table_infos"]

        # 1. 使用 LLM 对合并的表和字段数据根据需求过滤
        prompt = PromptTemplate(
            template=loder_prompt("filter_table_info"),
            input_variables=["query", "table_infos"],
        )
        # 定义 json 格式化输出对象
        output_parser = JsonOutputParser()
        # 组合 chain 链
        chain = prompt | llm | output_parser
        # 执行 chain
        result = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            }
        )

        # 2. 根据大模型返回结果过滤表和字段
        #    遍历时用浅拷贝 table_infos[:]，安全移除元素
        for table_info in table_infos[:]:
            # 如果表名不在 LLM 返回结果中，整张表移除
            if table_info["name"] not in result:
                table_infos.remove(table_info)
            else:
                # 表保留，但只保留 LLM 指定的字段
                selected_columns = result[table_info["name"]]
                # 遍历字段列表用浅拷贝，安全移除
                for column in table_info["columns"][:]:
                    if column["name"] not in selected_columns:
                        table_info["columns"].remove(column)

        # 修复: 原代码 f-string 内嵌双引号导致语法错误，改为单引号
        logger.info(f"过滤后的表信息: {[t['name'] for t in table_infos]}")
        return {"table_infos": table_infos}
    except Exception as e:
        logger.error(f"过滤表信息异常: {str(e)}")
        raise


# ===========================================================================
# 调试入口：用 mock 数据模拟过滤流程
# ===========================================================================
if __name__ == "__main__":

    # ------------------------------------------------------------------
    # 1. 构造 mock 输入数据（模拟 merge_retrieved_info 的输出）
    #    场景：用户查询「统计华北地区销售总额」
    #    合并后有 3 张表，LLM 会过滤掉 dim_customer，并精简各表字段
    # ------------------------------------------------------------------
    mock_table_infos: list[TableInfoStata] = [
        {
            "name": "fact_order",
            "role": "fact",
            "description": "订单事实表",
            "columns": [
                {"name": "order_amount", "type": "float", "role": "measure",
                 "examples": [10.2, 40.5], "description": "订单金额", "alias": ["amount"]},
                {"name": "order_id", "type": "varchar(32)", "role": "primary_key",
                 "examples": [], "description": "订单ID", "alias": []},
                {"name": "region_id", "type": "varchar(20)", "role": "foreign_key",
                 "examples": [1, 2, 3], "description": "地区维度外键", "alias": ["region_code"]},
                {"name": "order_date", "type": "date", "role": "dimension",
                 "examples": [], "description": "订单日期", "alias": ["date"]},
                {"name": "customer_id", "type": "varchar(20)", "role": "foreign_key",
                 "examples": [], "description": "客户外键", "alias": []},
            ],
        },
        {
            "name": "dim_region",
            "role": "dimension",
            "description": "地区维度表",
            "columns": [
                {"name": "region_id", "type": "varchar(20)", "role": "primary_key",
                 "examples": [1, 2, 3], "description": "地区ID", "alias": []},
                {"name": "region_name", "type": "varchar(50)", "role": "dimension",
                 "examples": ["华北", "华南"], "description": "地区名称", "alias": ["region"]},
                {"name": "region_code", "type": "varchar(10)", "role": "dimension",
                 "examples": ["HB", "HN"], "description": "地区编码", "alias": []},
            ],
        },
        {
            "name": "dim_customer",
            "role": "dimension",
            "description": "客户维度表",
            "columns": [
                {"name": "customer_id", "type": "varchar(20)", "role": "primary_key",
                 "examples": [], "description": "客户ID", "alias": []},
                {"name": "customer_name", "type": "varchar(50)", "role": "dimension",
                 "examples": [], "description": "客户名称", "alias": []},
            ],
        },
    ]

    # ------------------------------------------------------------------
    # 2. mock LLM —— 用 RunnableLambda 替换真实大模型
    #    filter_table 内部会执行 prompt | llm | output_parser
    #    llm 需要返回 AIMessage，JsonOutputParser 从 .content 解析 JSON
    # ------------------------------------------------------------------
    # 模拟 LLM 的判断结果：
    #   - 保留 fact_order，只留 order_amount + region_id（去掉 order_id/order_date/customer_id）
    #   - 保留 dim_region，只留 region_id + region_name（去掉 region_code）
    #   - 移除 dim_customer（与「销售总额」无关）
    mock_llm_result = '{"fact_order": ["order_amount", "region_id"], "dim_region": ["region_id", "region_name"]}'

    def mock_llm_func(_prompt_value):
        """模拟 LLM 返回，忽略输入，返回固定 JSON"""
        return AIMessage(content=mock_llm_result)

    mock_llm = RunnableLambda(mock_llm_func)

    # 关键：替换模块级 llm，filter_table 内部引用的 llm 会被替换为 mock
    # 因为 Python 函数在调用时从模块全局命名空间查找 llm
    llm = mock_llm  # noqa: F811

    # ------------------------------------------------------------------
    # 3. 构造 state 和 runtime
    # ------------------------------------------------------------------
    state: DataAgentState = {
        "query": "统计华北地区销售总额",
        "keywords": ["统计", "销售总额", "华北地区"],
        "table_infos": mock_table_infos,
    }

    runtime = MagicMock()
    runtime.stream_writer = lambda x: print(f"  [进度] {x}")
    runtime.context = {}

    # ------------------------------------------------------------------
    # 4. 执行过滤
    # ------------------------------------------------------------------
    async def main():
        print("=" * 70)
        print("开始执行 filter_table")
        print("=" * 70)

        print("\n--- 过滤前 ---")
        for t in mock_table_infos:
            col_names = [c["name"] for c in t["columns"]]
            print(f"  {t['name']} ({t['role']}): {col_names}")

        print(f"\n--- mock LLM 返回 ---\n  {mock_llm_result}")

        print("\n--- 执行过滤 ---")
        result = await filter_table(state, runtime)

        print("\n" + "=" * 70)
        print("过滤结果")
        print("=" * 70)

        filtered = result["table_infos"]
        print(f"\n📊 保留 {len(filtered)} 张表:")
        for t in filtered:
            col_names = [c["name"] for c in t["columns"]]
            print(f"  {t['name']} ({t['role']}): {col_names}")
            for c in t["columns"]:
                print(f"    - {c['name']} ({c['type']}, {c['role']}): {c['description']}")

        print("\n--- 过滤对比 ---")
        before_tables = [t["name"] for t in mock_table_infos]
        after_tables = [t["name"] for t in filtered]
        removed = set(before_tables) - set(after_tables)
        print(f"  移除的表: {removed if removed else '无'}")
        print(f"  保留的表: {after_tables}")

        print("\n" + "=" * 70)
        print("✅ 过滤完成")
        print("=" * 70)

    asyncio.run(main())
