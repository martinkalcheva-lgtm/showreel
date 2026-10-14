from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from service.dialogue_service import DialogueService
from repository.dialogue_state_repository import DialogueStateRepository
from engine.dialogue_engine import DialogueEngine
from infrastructure import database
from pathlib import Path

from task.action.builder import build_action_runner
from task.command.processor import CommandProcessor
from task.flow.loader import FlowLoader
from task.handler import TaskHandler, ChitChatHandler, KnowledgeHandler
from plan.turn_planner import TurnPlanner
from plan.turn_validator import TurnPlanValidator
from clarify.responder import ClarifyResponder
from task.flow.executor import FlowExecutor
from chitchat.responder import ChitChatResponder

from knowledge.intents import KNOWLEDGE_INTENTS
from knowledge.responder import KnowledgeResponder
from knowledge.registry import KnowledgeProviderRegistry
from knowledge.providers import FAQProvider,RAGProvider,OrderAPIProvider,ProductAPIProvider


async def get_session():
    """
    实际流程：
        进入 async with → 打开 session
        yield session → 把 session 交给repository函数使用
        路由函数执行完毕 → 回到 yield 之后
        退出 async with → 自动关闭 session ✅
    :return:
    """
    async with database.async_session() as session:  # 异步方式获取session  获取session要网络传输（耗时的）
        yield session


async def get_dialogue_state_repository(session: AsyncSession = Depends(get_session)):
    """
    创建 DialogueStateRepository 实例

    依赖链执行顺序：
       1. get_session() 打开 session 并 yield
       2. 这里拿到 session，创建 Repository
       3. Repository 被Service使用，Service被路由函数使用
       4. 路由函数返回后，get_session() 继续执行，自动关闭 session
    """
    return DialogueStateRepository(session=session)
    # 3. 函数返回后，FastAPI 继续执行 get_session() y


async def get_engine():
    # 1. 实例化命令处理器：用来修改对话状态（开启/暂停/恢复任务）
    # command_processor = CommandProcessor()
    # 2 实例化任务处理器（分任务），注入流程模板flow_list 和命令处理器
    # task_handler = TaskHandler(flows=flow_list, command_processor=command_processor)

    # 接收用户消息调用大模型，生成Command指令
    # turn_planner = TurnPlanner() # 意图分析器

    # 4. KnowledgeHandler：处理知识库问答（商品政策、FAQ）
    # knowledge_handler = KnowLedgeHandler(knowledge_intents=KNOWLEDGE_INTENTS) # 知识意图

    # 5. ClarifyResponder：参数缺失时，生成反问澄清话术
    # clarify_responder = ClarifyResponder() # 澄清

    # 6. TurnPlanValidator：校验大模型输出的指令是否合法
    # turn_plan_validator = TurnPlanValidator()

    # 组装全部组件，返回完整对话引擎


    base=Path(__file__).resolve().parents[2]
    flow_list = FlowLoader().load_many([
        base / "flow_config" / "user_flows.yml",
        base / "flow_config" / "system_flows.yml",
    ])

    return DialogueEngine(
        turn_planner=TurnPlanner(),
        task_handler=TaskHandler(
            flows=flow_list,
            command_processor=CommandProcessor(),
            action_runner=build_action_runner(),
            flow_executor=FlowExecutor()
        ),
        knowledge_handler=KnowledgeHandler(
            knowledge_intents=KNOWLEDGE_INTENTS,
            knowledge_responder=KnowledgeResponder(),
            provider_registry=KnowledgeProviderRegistry(
                [
                    ProductAPIProvider(),
                    OrderAPIProvider(),
                    FAQProvider(),
                    RAGProvider(),
                ]
            ),
        ),
        clarify_responder=ClarifyResponder(),
        turn_plan_validator=TurnPlanValidator(),
        chitchat_handler=ChitChatHandler(ChitChatResponder())
    )

async def get_dialogue_service(
        dialogue_state_repository: DialogueStateRepository = Depends(get_dialogue_state_repository),
        dialogue_engine: DialogueEngine = Depends(get_engine)
) -> DialogueService:
    return DialogueService(dialogue_state_repository=dialogue_state_repository, dialogue_engine=dialogue_engine)
