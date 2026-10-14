# 添加额外上下文信息的节点

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoStata
from app.core.log import logger
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository


async def add_extra_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    # 获取流式输出器
    writer = runtime.stream_writer
    # 输出进度状态信息
    writer({"stage":"添加额外上下文"})

    try:
        # 补充额外的时间信息
        today = datetime.today()
        # 日期
        date = today.strftime("%Y-%m-%d")
        # 星期
        weekday = today.strftime("%A")
        # 季度
        quarter = f"Q{(today.month - 1) // 3 + 1}"
        # 构建时间信息对象
        date_info=DateInfoStata(date=date,weekday=weekday,quarter=quarter)
        # 补充额外的数据库环境信息
        # 获取数仓查询操作对象
        dw_mysql_repository:DwMysqlRepository = runtime.context["dw_mysql_repository"]
        # 执行查询数据库版本和方言
        db_info=await dw_mysql_repository.get_db_info()

        logger.info(f"额外上下文信息添加，日期信息{date_info},数据库信息{db_info}")

        return {"date_info":date_info,"db_info":db_info}
    except Exception as e:
        logger.error(f"额外上下文信息添加异常：{str(e)}")
        raise

if __name__ == "__main__":
    # 模拟仓库对象，不和真实类冲突，不需要数据库连接
    class MockDwMysqlRepo:
        async def get_db_info(self):
            return {
                "db_type": "mysql",
                "version": "8.0.32",
                "sql_dialect": "mysql"
            }

    async def debug_main():
        # 1. 模拟state
        mock_state = {}

        # 2. 模拟Runtime运行环境
        runtime = MagicMock()
        def print_progress(msg):
            print(f"【节点进度】{msg}")
        runtime.stream_writer = print_progress
        runtime.context = {
            "dw_mysql_repository": MockDwMysqlRepo()
        }

        print("========== 开始执行 add_extra_context 节点 ==========")
        result = await add_extra_context(mock_state, runtime)

        print("\n========== 节点返回结果 ==========")
        print("date_info：", result["date_info"])
        print("db_info：", result["db_info"])

        print("\n=== 下游SQL生成节点会把这段塞入Prompt ===")
        date_info = result["date_info"]
        db_info = result["db_info"]
        prompt_text = f"""
基准时间信息：
今日日期：{date_info["date"]}
星期：{date_info["weekday"]}
当前季度：{date_info["quarter"]}
数据库类型：{db_info["db_type"]}
要求：生成符合MySQL语法的SQL
"""
        print(prompt_text)

    asyncio.run(debug_main())