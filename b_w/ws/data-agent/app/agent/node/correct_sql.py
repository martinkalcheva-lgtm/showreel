# 校正SQL的节点

import asyncio
from unittest.mock import MagicMock

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompts.prompt_loader import loder_prompt



async def correct_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("校正SQL")
    writer({"stage":"校正SQL"})
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
        # 获取sql
        sql = state["sql"]
        # 获取异常信息
        error = state["error"]


        # 创建提示词对象
        prompt = PromptTemplate(template=loder_prompt("correct_sql"),
                                input_variables=["query", "table_infos", "metric_infos", "date_info", "db_info","sql","error"])
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
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            "sql": sql,
            "error": error
        })
        logger.info(f"校验生成的正确sql语句\n：{result}")

        return {"sql": result}
    except Exception as e:
        logger.error(f"校验生成的正确sql语句异常:{str(e)}")
        raise


# ===================== 本地调试入口 =====================
if __name__ == "__main__":
    async def debug_main():
        # 模拟上游完整state（validate_sql校验失败后流入当前节点）
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
            "db_info": {"dialect": "mysql", "version": "8.0.32"},
            "sql": "SELECT SUM(wrong_column) FROM fact_order WHERE quarter = 'Q3'",
            "error": "Unknown column 'wrong_column' in 'field list'"
        }

        # 模拟Runtime
        runtime = MagicMock()
        def print_progress(msg):
            print(f"【节点进度】{msg}")
        runtime.stream_writer = print_progress

        # 拦截LLM调用，不请求真实大模型，直接返回修复后的SQL
        fixed_sql = """
SELECT SUM(order_amount) AS 订单总额
FROM fact_order
WHERE quarter = 'Q3'
"""
        from langchain_core.runnables import RunnableSequence
        async def mock_ainvoke(self, inputs):
            print("===== 送入校正SQL提示词的所有参数 =====")
            print("原始问题：", inputs["query"])
            print("待修复SQL：\n", inputs["sql"])
            print("报错信息：", inputs["error"])
            print("表结构：\n", inputs["table_infos"])
            return fixed_sql

        RunnableSequence.ainvoke = mock_ainvoke

        print("========== 开始执行 correct_sql 节点 ==========")
        output = await correct_sql(mock_state, runtime)

        print("\n========== 节点返回结果 ==========")
        print("修复完成后的SQL：")
        print(output["sql"])

    asyncio.run(debug_main())