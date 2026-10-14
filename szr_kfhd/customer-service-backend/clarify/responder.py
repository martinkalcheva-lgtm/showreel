# 澄清
from typing import List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
import json
from domain.messages import BotMessage
from domain.state import DialogueState
from infrastructure.llm import llm
from plan.models import ClarifyReason
from prompts.history_builder import HistoryBuilder
from prompts.loader import load_prompt


class ClarifyResponder:
    def build_clarify_message(
            self,
            reason: ClarifyReason,
            state: DialogueState,
    ) -> str:
        if reason is ClarifyReason.MULTIPLE_TRACKS:
            return "你这次同时提到了多个方向。我们先处理一个，你想先办业务还是先咨询信息呢？"

        if reason is ClarifyReason.MISSING_FOCUSED_OBJECT:
            return "请先发送你想咨询的对象，我再继续帮你看。"

        if reason is ClarifyReason.MISSING_KNOWLEDGE_INTENT:
            return "你是想了解商品信息、订单信息，还是售后配送规则呢？"

        if reason is ClarifyReason.MISSING_TRACK:
            return "你是想先处理业务问题，还是先咨询信息呢？"

        if reason is ClarifyReason.MISSING_TASK_COMMANDS:
            return "你这次是想办理什么业务呢？比如查订单、查物流，或者申请退款。"

        if reason is ClarifyReason.OBJECT_REQUIRES_INTENT:
            focused_object = state.focused_object
            if focused_object is not None and focused_object.type == "order":
                return "我已经收到这个订单了。你想查订单状态、查物流，还是申请退款呢？"
            if focused_object is not None and focused_object.type == "product":
                return "我已经收到这个商品了。你想了解它的商品信息、发货情况，还是售后相关问题呢？"

        return "我还需要再确认一下你的意思，你可以换个更具体的说法告诉我。"

    async def respond(
            self,
            state: DialogueState,
            reason: ClarifyReason,
    ) -> list[BotMessage]:
        message = state.pending_turn.user_message
        clarify_message = self.build_clarify_message(reason=reason, state=state)  # ① 基础话术
        # 把UserMessage对象，转换成LLM可读的字符串文本
        user_message = HistoryBuilder._render_user_message(message)
        # 读取当前会话全部历史turn轮次，组装对话历史字符串，给LLM做上下文
        history = HistoryBuilder.build(state.current_session().turns)
        # 将聚焦对象（订单/卡片）转为json字符串，传给提示词模板
        focused_object = json.dumps(state.focused_object.to_dict())

        prompt_text = load_prompt("clarify_respond")
        prompt = PromptTemplate.from_template(prompt_text, template_format="jinja2")
        chain = prompt | llm | StrOutputParser()
        rewritten = await chain.ainvoke(  # ② LLM 润色
            {
                "reason": reason.value,
                "clarify_message": clarify_message,
                "focused_object": focused_object,
                "history": history,
                "user_message": user_message,
            }
        )
        return [BotMessage(text=rewritten)]

if __name__ == '__main__':
    from domain.messages import FocusedObject
    import asyncio

    responder = ClarifyResponder()

    # 状态1：空状态（无聚焦对象）
    state = DialogueState(sender_id="user_001")
    # 状态2：已聚焦订单对象
    state_with_order = DialogueState(
        sender_id="user_001",
        focused_object=FocusedObject(id="ORDER_10001", type="order", title="订单10001"),
    )
    # 状态3：已聚焦商品对象
    state_with_product = DialogueState(
        sender_id="user_001",
        focused_object=FocusedObject(id="SKU_20001", type="product", title="纯棉T恤"),
    )

    def run_case(name: str, reason: ClarifyReason, st: DialogueState = state):
        msg = responder.build_clarify_message(reason, st)
        print(f"[{name}] {msg}")

    # 1. 多轨道 → 让用户选办业务还是咨询
    run_case(" 1.多轨道        ", ClarifyReason.MULTIPLE_TRACKS)
    # # 2. 缺聚焦对象 → 让用户先发对象
    # run_case(" 2.缺聚焦对象     ", ClarifyReason.MISSING_FOCUSED_OBJECT)
    # # 3. 知识轨道缺意图 → 问咨询哪类信息
    # run_case(" 3.缺知识意图     ", ClarifyReason.MISSING_KNOWLEDGE_INTENT)
    # # 4. 缺轨道 → 问办业务还是咨询
    # run_case(" 4.缺轨道        ", ClarifyReason.MISSING_TRACK)
    # # 5. task 轨道缺 commands → 问办什么业务
    # run_case(" 5.缺任务指令     ", ClarifyReason.MISSING_TASK_COMMANDS)
    # # 6. 有订单对象缺意图 → 订单话术
    # run_case(" 6.订单缺意图     ", ClarifyReason.OBJECT_REQUIRES_INTENT, st=state_with_order)
    # # 7. 有商品对象缺意图 → 商品话术
    # run_case(" 7.商品缺意图     ", ClarifyReason.OBJECT_REQUIRES_INTENT, st=state_with_product)
    # # 8. 对象缺意图但没有聚焦对象 → 兜底话术
    # run_case(" 8.无对象兜底     ", ClarifyReason.OBJECT_REQUIRES_INTENT)
    # # 9. 未单独处理的 reason（如流程不存在）→ 兜底话术
    # run_case(" 9.未知流程兜底   ", ClarifyReason.UNKNOWN_TASK_FLOW)

    # 10.（可选）端到端验证 respond，会真实调用 LLM，需要 .env 配置
    # from domain.messages import UserMessage, MessageType
    # from domain.state import Turn
    # state.pending_turn = Turn(
    #     turn_id="t1",
    #     user_message=UserMessage(sender_id="user_001", message_id="m1",
    #                              type=MessageType.TEXT, text="我想问点事"),
    #     bot_messages=[],
    # )
    # state.start_session()
    # result = asyncio.run(responder.respond(state, ClarifyReason.MULTIPLE_TRACKS))
    # print(f"[10.LLM润色     ] {result[0].text}")

