# itwwy/engine/dialogue_engine.py
from cgitb import handler

import time
from datetime import datetime

from plan.turn_planner import TurnPlanner
from task.flow.steps import CollectFlowStep
from domain.state import DialogueState
from domain.messages import UserMessage, ProcessResult, BotMessage, MessageType, FocusedObject
from task.command.models import Command, SetSlotsCommand
from task.flow.flows import FlowsList
from task.handler import TaskHandler, ChitChatHandler, KnowledgeHandler

from plan.turn_validator import TurnPlanValidator
from knowledge.intents import KNOWLEDGE_INTENTS
from plan.models import ClarifyReason
from clarify.responder import ClarifyResponder


class DialogueEngine:
    def __init__(
            self,
            turn_planner: TurnPlanner,
            task_handler: TaskHandler,
            knowledge_handler: KnowledgeHandler,
            chitchat_handler: ChitChatHandler,
            clarify_responder: ClarifyResponder,
            turn_plan_validator: TurnPlanValidator
    ) -> None:
        self.turn_planner = turn_planner
        self.task_handler = task_handler
        self.knowledge_handler = knowledge_handler
        self.chitchat_handler = chitchat_handler
        self.clarify_responder = clarify_responder
        self.turn_plan_validator = turn_plan_validator

    async def process_message(self, dialogue_state: DialogueState,
                            user_message: UserMessage) -> ProcessResult:
        # TODO (用户的消息---->LLM路由(三条轨道的某一条) 执行某一条)
        # 1. 准备会话
        self._prepare_session(dialogue_state)
        # 2. 开启本轮turn
        self._begin_turn(dialogue_state, user_message)

        # 3. 按消息类型分流
        if user_message.type is MessageType.TEXT:
            messages = await self._handle_text_message(dialogue_state)
        else:
            # 对象消息
            dialogue_state.set_focused_object(FocusedObject.from_dict(user_message.object.to_dict()))
            messages = await self._handle_object_message(message=user_message, state=dialogue_state)


        # 4. 把本轮回复写入turn
        dialogue_state.pending_turn.bot_messages.extend(messages)
        # 提交:turn 进入 session 历史
        dialogue_state.commit_turn()

        # 5. 组装返回结果
        return ProcessResult(
            sender_id=user_message.sender_id,
            message_id=user_message.message_id,
            messages=messages,
        )



    """
    A.流程正等着要订单号时，点了订单
    B.没有任何流程时，点了订单
    C.流程进行中、但当前不缺这个对象时，点了订单
    """
    async def _handle_object_message(
            self,
            message: UserMessage,
            state: DialogueState,) -> list[BotMessage]:
        # 判断当前点击的对象，能不能填进当前流程正缺的卡槽中
        commands = self._resolve_object_commands(
            message=message,
            state=state,
            flows=self.task_handler.flows,)

        if commands:
            # 场景 A:对象能填当前槽 → 转成命令,推进流程
            return await self.task_handler.handle(commands=commands, state=state)

        # 没有匹配到 slot。如果用户正在一个流程中,不打断,让流程继续。
        if state.active_task is not None:
            # 场景 C:在流程里但槽不匹配 → 不打断,空命令让流程继续
            return await self.task_handler.handle(commands=[], state=state)

            # 场景 B:没有流程 → 澄清
        return await self.clarify_responder.respond(
            state=state,
            reason=ClarifyReason.OBJECT_REQUIRES_INTENT,
        )

    def _resolve_object_commands(
            self,
            message: UserMessage,
            state: DialogueState,
            flows: FlowsList,
    ) -> list[Command]:
        # 拿到当前的点击对象
        message_object = message.object
        if message_object is None:
            return []

        # 拿到这个点击对象的类型
        object_type = message_object.type.strip().lower()

        # 如果类型是order
        if object_type == "order":
            if self._flow_has_unfilled_collect_slot(state, flows, "order_number"):
                return [SetSlotsCommand(
                    command="set_slots",
                    slots={"order_number": message_object.id},
                )]
            return []

        # 如果类型是product
        if object_type == "product":
            if self._flow_has_unfilled_collect_slot(state, flows, "product_id"):
                return [SetSlotsCommand(
                    command="set_slots",
                    slots={"product_id": message_object.id},
                )]
            return []

        return []

    @staticmethod
    def _flow_has_unfilled_collect_slot(
            state: DialogueState,flows: FlowsList,slot_name: str,) -> bool:
        """检查当前流程是否定义了名为 slot_name 的收集槽且尚未填充。"""
        active_task = state.active_task
        # ① 没有活跃流程
        if active_task is None:
            return False

        # ② 流程 id 查不到(防御)
        flow = flows.get_flow_by_id(active_task.flow_id)
        if flow is None:
            return False

        # ③ 这个槽已经填了
        if active_task.slots.get(slot_name):
            return False


        # ④ 流程里有没有收集这个槽的步骤
        for step in flow.steps:
            # 这里改了
            if isinstance(step, CollectFlowStep) and step.slot_name == slot_name:
                return True
        return False




    async def _handle_text_message(self, dialogue_state: DialogueState) -> list[BotMessage]:
        # 1.调LLM生成本轮计划（确定任务轨道
        turn_plan = await self.turn_planner.predict(dialogue_state, self.task_handler.flows)

        # 2. 防幻觉校验：LLM 可能编造流程名/意图，或一次多意图
        validation = self.turn_plan_validator.validate(
            state=dialogue_state,
            turn_plan=turn_plan,
            flow_list=self.task_handler.flows,  # 注意：你 validator 的形参名叫 flow_list
            intents=KNOWLEDGE_INTENTS,
        )
        if not validation.valid:
            return await self.clarify_responder.respond(
                state=dialogue_state, reason=validation.reason,
            )

        # # ============【这里插入防幻觉校验逻辑】============
        # # 实例化校验器，执行校验
        # validator = TurnPlanValidator()
        # validation = validator.validate(
        #     state=dialogue_state,
        #     turn_plan=turn_plan,
        #     flow_list=self.task_handler.flows,
        #     intents=KNOWLEDGE_INTENTS
        # )
        # # 文本校验失败，调用澄清回复，直接返回，不再执行后面分发逻辑
        # if not validation.valid:
        #     return await self.clarify_responder.respond(state=dialogue_state, reason=validation.reason)
        # # =================================================

        # 3. 按轨道分发
        if turn_plan.task is not None:
            return await self.task_handler.handle(
                commands=turn_plan.task.commands,
                state=dialogue_state,
            )
        elif turn_plan.knowledge is not None:
            # 3.2 信息检索
            return await self.knowledge_handler.handle(intents=turn_plan.knowledge.intents, state=dialogue_state)
        else:
            # 3.3 闲聊
            return await self.chitchat_handler.handle(state=dialogue_state)





    def _begin_turn(self, dialogue_state: DialogueState, user_message: UserMessage) -> None:
        """
        开始一个turn
        """
        dialogue_state.begin_turn(user_message)

    def _prepare_session(self,dialogue_state: DialogueState):
        """
        准备会话
        """
        # 1. 获取当前会话
        session = dialogue_state.current_session()

        # 2. 如果当前会话不存在，则创建一个会话
        if session is None:
            dialogue_state.start_session()
            return

        # 3. 判断会话是否超时
        now = time.time()
        if now - session.last_activity_at > 60 * 60: # 1小时
            # 关闭会话
            dialogue_state.close_current_session()
            # 重置运行时状态
            dialogue_state.reset_runtime_state_for_new_session()
            # 创建会话
            dialogue_state.start_session()
        else:
            # 更新会话（会话续期
            session.last_activity_at = now