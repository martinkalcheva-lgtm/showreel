# 生成sql的节点

import asyncio
from unittest.mock import MagicMock

import yaml
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompts.prompt_loader import loder_prompt


async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("生成SQL")
    writer({"stage": "生成SQL"})
    try:
        # 获取用户查询
        query = state["query"]
        # 获取表数据列表
        table_infos = state["table_infos"]
        # 获取指标数据列表
        metric_infos = state["metric_infos"]
        # 获取时间信息
        date_info = state["date_info"]
        # 获取数据库信息
        db_info = state["db_info"]

        # 创建提示词对象
        prompt = PromptTemplate(template=loder_prompt("generate_sql"),
                                input_variables=["query", "table_infos", "metric_infos", "date_info", "db_info"])
        # 构建json转换对象--> 此处解析必须使用文本解析方式
        output_parser = StrOutputParser()
        # 构建查询链
        chain = prompt | llm | output_parser
        # 执行查询
        result = await chain.ainvoke({
            "query": query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False)
        })
        logger.info(f"生成的sql语句\n：{result}")

        return {"sql": result}
    except Exception as e:
        logger.error(f"生成的sql语句失败:{str(e)}")
        raise


# ===================== 本地调试入口 =====================
if __name__ == "__main__":
    async def debug_main():
        # ========== 1. 模拟完整State数据（模拟前面所有节点输出） ==========
        mock_state = {
            "query": "统计本季度订单总额",
            "table_infos": [
                {
                    "name": "fact_order",
                    "role": "事实表",
                    "description": "订单明细表",
                    "columns": [
                        {"name": "order_amount", "type": "decimal", "role": "指标", "examples": [], "description": "订单金额", "alias": []},
                        {"name": "quarter", "type": "string", "role": "维度", "examples": [], "description": "季度", "alias": []}
                    ]
                }
            ],
            "metric_infos": [
                {
                    "name": "订单总额",
                    "description": "所有订单金额合计",
                    "relevant_columns": ["order_amount"],
                    "alias": []
                }
            ],
            "date_info": {"date": "2026-08-11", "weekday": "Tuesday", "quarter": "Q3"},
            "db_info": {"dialect": "mysql", "version": "8.0.32"}
        }

        # ========== 2. 模拟Runtime、模拟LLM（不调用真实大模型） ==========
        runtime = MagicMock()
        def print_progress(msg):
            print(f"【节点进度】{msg}")
        runtime.stream_writer = print_progress

        # mock llm，直接返回一段测试SQL，不需要联网
        mock_sql = """
SELECT SUM(order_amount) AS 订单总额
FROM fact_order
WHERE quarter = 'Q3'
"""
        # 模拟链调用，直接返回预设SQL
        original_chain_invoke = None
        from langchain_core.runnables import RunnableSequence
        async def mock_ainvoke(self, inputs):
            print("===== 送入LLM的完整上下文 =====")
            print("query：", inputs["query"])
            print("\ntable_infos yaml：\n", inputs["table_infos"])
            print("\nmetric_infos yaml：\n", inputs["metric_infos"])
            print("\ndate_info yaml：\n", inputs["date_info"])
            print("\ndb_info yaml：\n", inputs["db_info"])
            return mock_sql

        RunnableSequence.ainvoke = mock_ainvoke

        print("========== 开始执行 generate_sql 节点 ==========")
        output = await generate_sql(mock_state, runtime)

        print("\n========== 节点返回结果 ==========")
        print("最终生成SQL：")
        print(output["sql"])

    asyncio.run(debug_main())