from chitchat.responder import ChitChatResponder
from knowledge.registry import KnowledgeProviderRegistry
from knowledge.responder import KnowledgeResponder
from task.command.processor import CommandProcessor
from domain.messages import BotMessage
from domain.state import DialogueState
from task.command.models import Command
from task.flow.executor import FlowExecutor
from task.flow.flows import FlowsList
from task.action.runner import ActionRunner
from knowledge.intents import KnowledgeIntent
from knowledge.providers import KnowledgeChunk



class KnowledgeHandler:

    def __init__(
            self,
            knowledge_intents: dict[str, KnowledgeIntent],
            provider_registry: KnowledgeProviderRegistry,
            knowledge_responder: KnowledgeResponder):

        self.knowledge_intents = knowledge_intents
        self.provider_registry = provider_registry
        self.knowledge_responder = knowledge_responder

    async def handle(self, intents: list[str], state: DialogueState) -> list[BotMessage]:

        # 1. 根据意图寻找知识来源（知识提供者id列表）
        provider_ids: list[str] = self._get_provider_ids_by_intents(intents)

        # 2. 从每个 provider 检索知识片段
        chunks: list[KnowledgeChunk] = []
        for provider_id in provider_ids:
            provider = self.provider_registry.get(provider_id)
            current_chunks = await provider.retrieve(state)
            chunks.extend(current_chunks)

        # 3. 用知识生成回复
        return await self.knowledge_responder.respond(
            user_message=state.pending_turn.user_message,
            recent_turns=state.current_session().turns,
            chunks=chunks
        )

    def _get_provider_ids_by_intents(self, intents: list[str]) -> list[str]:
        provider_ids: list[str] = []
        for intent in intents:
            provider_ids.extend(self.knowledge_intents[intent].provider_ids)
        return list(set(provider_ids))








class ChitChatHandler:
    def __init__(self, responder: ChitChatResponder):
        self.responder = responder

    async def handle(self, state: DialogueState) -> list[BotMessage]:
        pending_turn = state.pending_turn
        user_message = pending_turn.user_message
        recent_turns = state.current_session().turns

        return await self.responder.respond(
            user_message=user_message,
            recent_turns=recent_turns,
        )




class TaskHandler:

    def __init__(
            self,
            flows: FlowsList,
            command_processor: CommandProcessor,
            action_runner: ActionRunner,
            flow_executor: FlowExecutor
    ):
        self.flows = flows
        self.command_processor = command_processor
        self.action_runner = action_runner
        self.flow_executor = flow_executor

    async def handle(self, commands: list[Command], state: DialogueState) -> list[BotMessage]:
        # 阶段1：CommandProcessor 进行状态的修改
        self.command_processor.run(commands, state, self.flows)

        # 阶段2：FlowExecutor 进行任务/流程的推进
        messages = await self.flow_executor.run_task(state, self.flows, self.action_runner)

        # 返回流程执行器得到的消息
        return messages