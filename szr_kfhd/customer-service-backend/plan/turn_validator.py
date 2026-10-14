from sys import intern
from typing import Dict

from domain.state import DialogueState
from knowledge import intents
from knowledge.intents import KnowledgeIntent
from plan.models import TurnPlan, TurnPlanValidationResult, ClarifyReason
from task.command.models import SetSlotsCommand, StartFlowCommand, ResumeFlowCommand, CancelFlowCommand
from task.flow.flows import FlowsList

class TurnPlanValidator:
    def validate(self,
            state:DialogueState,
            turn_plan: TurnPlan,
            flow_list: FlowsList,
            intents: Dict[str,KnowledgeIntent]
    ) -> TurnPlanValidationResult:
        # 计算命中几个轨道
        active_tracks = self._active_tracks(turn_plan)

        # 1.是否没有命中的轨道
        if not active_tracks:
            return self._reject(ClarifyReason.MISSING_TRACK)

        # 2.是否命中多条轨道
        if len(active_tracks) > 1:
            return self._reject(ClarifyReason.MULTIPLE_TRACKS)

        # 3.获取唯一的轨道
        active_track = active_tracks[0]

        # 4.判断轨道到底是哪一个
        if active_track == "task":
            # 4.1业务任务轨道
            return self._validate_task(turn_plan, flow_list)

        if active_track == "knowledge":
            # 4.2 信息咨询任务轨道
            return self._validate_knowledge(state, turn_plan, intents)

        # 校验通过：True
        return TurnPlanValidationResult(valid=True)

    def _validate_knowledge(
            self,
            state: DialogueState,
            turn_plan: TurnPlan,
            intents: Dict[str, KnowledgeIntent]) -> TurnPlanValidationResult:
        knowledge_plan = turn_plan.knowledge

        if knowledge_plan is None or not knowledge_plan.intents:
            return self._reject(ClarifyReason.MISSING_KNOWLEDGE_INTENT)

        focused_object = state.focused_object
        for intent in knowledge_plan.intents:
            intent_meta = intents[intent]
            required_object = intent_meta.requires_object
            if required_object is not None:
                if focused_object is None or focused_object.type != required_object:
                    return self._reject(ClarifyReason.MISSING_FOCUSED_OBJECT)

        return TurnPlanValidationResult(valid=True)

    def _validate_task(self,
            turn_plan: TurnPlan,flows: FlowsList,) -> TurnPlanValidationResult:
        """4.1业务任务轨道验证"""
        task_plan = turn_plan.task

        # 第一重：commands 不能为空
        if task_plan is None or not task_plan.commands:
            return self._reject(ClarifyReason.MISSING_TASK_COMMANDS)

        # 第二重：每个command 都得是认识的类型
        allowed = (StartFlowCommand,ResumeFlowCommand,CancelFlowCommand,
        SetSlotsCommand)
        if not all(isinstance(cmd,allowed) for cmd in task_plan.commands):
            return self._reject(ClarifyReason.INVALID_TASK_COMMANDS)

        # 第三重：不难一次开多个流程
        start_commands = [cmd for cmd in task_plan.commands if isinstance(cmd, StartFlowCommand)]
        if len(start_commands) > 1:
            return self._reject(ClarifyReason.MULTIPLE_TASK_FLOWS)

        # 第四重：要开的流程必须真实存在
        if start_commands:
            flow = flows.get_flow_by_id(start_commands[0].flow)
            if flow is None:
                return self._reject(ClarifyReason.UNKNOWN_TASK_FLOW)
        # 校验成功
        return TurnPlanValidationResult(valid=True)

    @staticmethod
    def _active_tracks(turn_plan: TurnPlan) -> list[str]:
        """
        计算命中了几个轨道
        """
        active_tracks:list[str] = []

        if turn_plan.task is not None:
            active_tracks.append("task") # 轨道的名字

        if turn_plan.knowledge is not None:
            active_tracks.append("knowledge") # 轨道的名字

        if turn_plan.chitchat is not None:
            active_tracks.append("chitchat") # 轨道的名字

        return active_tracks

    def _reject(self,reason:ClarifyReason) -> TurnPlanValidationResult:
        return TurnPlanValidationResult(
            valid=False,
            reason=reason
        )


if __name__ == "__main__":
    import json
    from plan.models import TurnPlan
    from knowledge.intents import KnowledgeIntent

    # Mock对象
    class MockDialogueState:
        focused_object = None
    class MockProduct:
        type = "product"

    # 构造意图
    intent_price = KnowledgeIntent(
        id="query_product_price",
        description="查询商品价格",
        requires_object="product"
    )
    mock_intents = {"query_product_price": intent_price}
    validator = TurnPlanValidator()

    # 合法场景：有商品对象 ✅
    state_ok = MockDialogueState()
    state_ok.focused_object = MockProduct()
    plan1 = TurnPlan.from_dict(json.loads
    ('{"task":null,"knowledge":{"intents":["query_product_price"]},"chitchat":null}'))
    print("Case1 ✅",
          validator.validate(
              state=state_ok,
              turn_plan=plan1,
              flow_list=None,
              intents=mock_intents))

    # 缺失对象 ❌ MISSING_FOCUSED_OBJECT
    state_empty = MockDialogueState()
    state_empty.focused_object = None
    plan2 = TurnPlan.from_dict(json.loads('{"task":null,"knowledge":{"intents":["query_product_price"]},"chitchat":null}'))
    print("Case2 ❌", validator.validate(state=state_empty, turn_plan=plan2, flow_list=None, intents=mock_intents))
