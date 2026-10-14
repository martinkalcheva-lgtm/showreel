# 校验SQL的节点

import asyncio
from unittest.mock import MagicMock

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompts.prompt_loader import loder_prompt


async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("校验SQL")
    writer({"stage": "校验SQL"})
    # 获取生成sql
    sql = state["sql"]
    # 获取数仓操作对象
    dw_mysql_repository=runtime.context["dw_mysql_repository"]
    # 捕获验证sql的异常信息
    try:
        # 执行验证sql
        await dw_mysql_repository.validate_sql(sql)
        # 无异常 None
        logger.info(f"sql验证正确：{sql}")
        return {"error":None}
    except Exception as e:
        logger.info(f"sql验证失败：{sql}")
        return {"error":str(e)}


# ===================== 本地调试入口 =====================
if __name__ == "__main__":
    # 模拟数据库仓库对象，不需要真实数据库连接
    class MockDwMysqlRepo:
        async def validate_sql(self, sql_text):
            # 模拟逻辑：包含错误关键字就抛出异常，用来测试成功/失败两种分支
            if "error_table" in sql_text or "bad_column" in sql_text:
                raise Exception("表或字段不存在，SQL语法校验失败")
            # 正常SQL不抛异常

    async def debug_main():
        # ========== 模拟上游state，里面存放generate_sql产出的SQL ==========
        mock_state = {
            "sql": "SELECT SUM(order_amount) AS 订单总额 FROM fact_order WHERE quarter = 'Q3'"
            # 切换成下面这条可以测试校验失败分支
            # "sql": "SELECT SUM(bad_column) FROM error_table"
        }

        # 模拟Runtime环境
        runtime = MagicMock()
        def print_progress(msg):
            print(f"【节点进度】{msg}")
        runtime.stream_writer = print_progress
        runtime.context = {
            "dw_mysql_repository": MockDwMysqlRepo()
        }

        print("========== 开始执行 validate_sql 节点 ==========")
        result = await validate_sql(mock_state, runtime)

        print("\n========== 节点返回结果 ==========")
        print("error字段值：", result["error"])
        if result["error"] is None:
            print("✅ SQL校验通过")
        else:
            print("❌ SQL校验失败，错误信息：", result["error"])

    asyncio.run(debug_main())