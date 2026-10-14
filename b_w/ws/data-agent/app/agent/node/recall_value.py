# 召回字段取值信息节点

import asyncio

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompts.prompt_loader import loder_prompt

async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):
		"""召回字段取值：之前是将字段取值存储到了es中，索引根据关键字和条件去es全文检索获取值数据"""
		logger.info("【开始执行recall_value】")
		# 获取流式输出器 和 输出进度状态信息
		writer = runtime.stream_writer
		writer({"stage":"召回字段取值"})

		try:
			# 获取用户问题 和 抽取到的关键字
			query = state['query']
			keywords = state['keywords']

			# 获取字段值es操作对象
			value_es_repository = runtime.context['value_es_repository']

			# 调用大模型
			prompt = PromptTemplate(
				template=loder_prompt("extend_keywords_for_value_recall"),
				input_variables=["query"],
			)
			output_parser =JsonOutputParser()
			chain = prompt | llm | output_parser
			result = await chain.ainvoke({"query":query})

			keywords = list(set(keywords + result))
			values_map: dict[str,ValueInfoEs] = {}
			for keyword in keywords:
				values:list[ValueInfoEs]=await value_es_repository.search(keyword)
				for value in values:
					# 获取字段值的id
					value_id = value['id']
					# 判断不存在添加
					if value_id not in values_map:
						# 添加数据到map中
						values_map[value_id] = value

			retrieves_values = list(values_map.values())
			logger.info(f"召回字段取值：{list(values_map.keys())}")

			logger.info("【recall_value执行结束，准备返回结果】")
			return {"retrieved_values":retrieves_values}

		except Exception as e:
			logger.error(f"召回字段取值异常：{str(e)}")
			raise