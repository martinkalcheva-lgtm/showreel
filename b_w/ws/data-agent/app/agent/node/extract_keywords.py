# 关键字抽取节点
import asyncio

import jieba
import jieba.analyse
from langgraph.runtime import Runtime
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def extract_keywords(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		# 获取流式输出器
		writer = runtime.stream_writer
		# 输出进度状态器
		writer({"stage":"抽取关键字"})

		try:
			# 获取用户查询问题
			query = state['query']
			# 定义返回指定词性的元组
			allow_pos = (
				"n",  # 名词: 数据、服务器、表格
				"nr",  # 人名: 张三、李四
				"ns",  # 地名: 北京、上海
				"nt",  # 机构团体名: 政府、学校、某公司
				"nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
				"v",  # 动词: 运行、开发
				"vn",  # 名动词: 工作、研究
				"a",  # 形容词: 美丽、快速
				"an",  # 名形词: 难度、合法性、复杂度
				"eng",  # 英文
				"i",  # 成语
				"l",  # 常用固定短语
			)

			# 使用jieba从用户的查询信息中提取关键，基于TF-IDF算法实现
			#jieba分词这个工具 进行关键字提取 为了避免语义丢失 在state返回之前 我们原始的语义 拼接
			keywords:list[str]=jieba.analyse.extract_tags(query,allowPOS=allow_pos)

			# 避免在使用jieba进行题词后，对关键信息出现丢失请求，将查询query添加到keywords中
			# 同样也要避免出现提取关键字后和原问题重复的情况，需要进行去重
			keywords=list(set(keywords + [query]))
			logger.info(f"抽取关键字:{keywords}")

			# 获取用户查询的关键字列表后，返回进行下一步处理即可
			return {"keywords":keywords}

		except Exception as e:
			logger.error(f"抽取关键字异常：{str(e)}")
			raise

# ---------------- 单元测试入口 ----------------
if __name__ == "__main__":
	def mock_writer(msg):
		print(f"[SSE推送] {msg}")

	class MockRuntime:
		stream_writer = lambda self, msg: mock_writer(msg)

	mock_runtime = MockRuntime()

	test_queries = [
        "统计各个省份的订单数量",
        "查询华东地区2025年的销售GMV",
        "北京市有多少用户，他们的订单金额是多少",
    ]

	async def test_run():
		for q in test_queries:
			print(f"\n==== 用户问题：{q} ====")
			state: DataAgentState = {"query": q}
			result = await extract_keywords(state, mock_runtime)
			print(f"输出keywords = {result['keywords']}")

	asyncio.run(test_run())