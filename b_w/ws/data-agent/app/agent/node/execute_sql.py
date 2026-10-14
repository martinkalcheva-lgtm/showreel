# SQL执行节点

import asyncio
from unittest.mock import MagicMock

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def execute_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    # writer("执行SQL")
    writer({"stage": "执行SQL"})
    try:

        # 获取sql
        sql = state["sql"]
        # 获取数仓操作对象
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        # 执行sql
        result = await dw_mysql_repository.execute_sql(sql)

        # 输出执行结果
        logger.info(f"执行sql的结果{result}")
        # 解析处理结果
        writer({"result": result})
    except Exception as e:
        logger.error(f"执行sql的结果异常：{str(e)}")
        raise


# ===================== 本地调试入口 =====================
if __name__ == "__main__":
    # 模拟仓库对象，不需要真实数据库
    class MockDwMysqlRepo:
        async def execute_sql(self, sql_text):
            # 模拟SQL执行，直接返回假数据
            print(f"【模拟执行SQL】{sql_text}")
            # 模拟查询返回结果
            return [{"订单总额": 862500}]

    async def debug_main():
        # 模拟上游state，存放校验通过的SQL
        mock_state = {
            "sql": "SELECT SUM(order_amount) AS 订单总额 FROM fact_order WHERE quarter = 'Q3'"
        }

        # 模拟Runtime
        runtime = MagicMock()
        def print_progress(msg):
            print(f"【节点进度】{msg}")
        runtime.stream_writer = print_progress
        runtime.context = {
            "dw_mysql_repository": MockDwMysqlRepo()
        }

        print("========== 开始执行 execute_sql 节点 ==========")
        await execute_sql(mock_state, runtime)

    asyncio.run(debug_main())