# task/flow/executor.py
import asyncio
from domain.state import DialogueState
from domain.contexts import (
    TaskContext,
    StartedSystemContext,
    InterruptedSystemContext,
    CanceledSystemContext,
    ResumedSystemContext,
    CollectedSystemContext
)

from task.flow.flows import FlowsList
from task.action.runner import ActionRunner, ActionCall
from domain.messages import BotMessage
from task.action.base import ActionResult
from task.flow.steps import FlowStep, StartFlowStep, EndFlowStep, CollectFlowStep, ActionFlowStep
from task.flow.links import StaticLink, ConditionalLink, FallbackLink


class FlowExecutor:
    """
    流程执行器：推进yaml中定义的业务任务流程以及系统任务流程
    """

    async def run_task(self, state: DialogueState, flows: FlowsList, action_runner: ActionRunner):

        messages: list[BotMessage] = []
        while True:  # 找要执行的流程步骤

            # 1. 取"下一个"要执行的单个动作:沿流程推进 step,遇 action step 返回其 ActionCall;
            #  若已无活跃任务可推进,则返回 action_listen 哨兵(该等用户输入了)
            action_call: ActionCall = self.advance_until_action(state, flows)

            # 2. 当action_name是action_listen的时候，结束流程，并返回消息，等待下一轮的用户输入
            if action_call.action_name == "action_listen":
                break
            else:
                # 3. 如果是其他类型的action，则执行action
                action_result: ActionResult = await action_runner.run(action_call, state)
                state.set_slots(action_result.slot_updates)
                messages.extend(action_result.messages)
                """
        slot_updates = {"order_status": "已发货"}   ← set_slots 写回 state
        messages  = [BotMessage("您的订单已发货，单号...")]  ← extend 收进 messages
                """

        # 4. 返回消息，等待下一轮的用户输入
        return messages

    def advance_until_action(self, state: DialogueState, flows: FlowsList) -> ActionCall:
        while True:
            # 1.获取当前任务上下问对象：系统任务优先
            current_active_task = state.current_active_task()

            # 2. 如果当前没有任务，手动返回action_listen，等待用户输入
            # 两种典型情况：
            # - 业务流程刚跑完 end 步骤，active_task 被清空，又没有系统过场
            # - 用户刚启动会话，根本还没开任何任务
            if current_active_task is None:
                return ActionCall(action_name="action_listen")

            # 3.获取当前流程对象(找到yaml里的具体流程信息)
            flow = flows.get_flow_by_id(current_active_task.flow_id)

            # 4. 获取当前step
            step = flow.get_step_by_id(current_active_task.step_id)

            # 5. 运行当前step
            action_call = self._run_step(state, step, flows)

            # 6. 如果step的类型是action,退出while true
            if action_call is not None:
                return action_call

    def _run_step(self, state: DialogueState, step: FlowStep, flows: FlowsList) -> ActionCall | None:

        if isinstance(step, StartFlowStep):
            return self._run_start_step(step, state)
        if isinstance(step, EndFlowStep):
            return self._run_end_step(state)
        if isinstance(step, CollectFlowStep):
            return self._run_collect_step(step, state, flows)
        if isinstance(step, ActionFlowStep):
            return self._run_action_step(step, state)

    def _run_collect_step(self, step: CollectFlowStep, state: DialogueState, flows: FlowsList):

        # 1. 尝试自动补槽
        self._try_to_fill_collect_slot_focused_object(state, step)

        # 2. 判断槽位是否已经填过
        if state.active_task.slots.get(step.slot_name):
            # 填过则直接执行下一步
            self._advance_next_step(state, step)
            return None
        else:
            # 没填过则启动系统过场：补槽任务CollectedSystemContext
            state.start_active_system_task(CollectedSystemContext(
                flow_id="system_collect_information",
                step_id=flows.get_flow_by_id('system_collect_information').start_step().id,
                slot_name=step.slot_name,
                response=step.response.model_dump(mode="json")
            ))
            return None

    def _try_to_fill_collect_slot_focused_object(self, state: DialogueState, step: CollectFlowStep):

        if state.focused_object is None:
            return None

        if step.slot_name == 'order_number' and state.focused_object.type == "order":
            state.set_slots({step.slot_name: state.focused_object.id})

        if step.slot_name == "product_id" and state.focused_object.type == "product":
            state.set_slots({step.slot_name: state.focused_object.id})



    def _run_action_step(self, step: ActionFlowStep, state: DialogueState) -> ActionCall:
        # 1. 推进下一步
        self._advance_next_step(state, step)
        # 2. 构造 ActionCall
        action_call = self._build_action_call(state, step)
        # 3. 退出内层让外层执行
        return action_call

    def _build_action_call(self, state, step) -> ActionCall:
        # 1. 获取action_name (action_listen/action_response/action_xxx)
        # 2. 获取action_kwargs (构建参数)
        action_name = step.action
        action_kwargs = step.args
        # action_kwargs有可能有:结构有可能是一个str、dict、或者空字典{}
        # str: "context.response"
        if isinstance(action_kwargs, str):
            action_kwargs = state.active_system_task.model_dump(mode="json")[action_kwargs.split(".")[1]]
        return ActionCall(action_name=action_name, action_kwargs=action_kwargs)





    def _run_end_step(self, state: DialogueState) -> None:
        if state.active_system_task:
            # 清空state中系统任务流程上下文
            state.end_active_system_task()
        else:
            # 清空state中业务任务流程上下文
            state.end_active_task()
        return None







    def _run_start_step(self, step: StartFlowStep, state: DialogueState) -> None:
        # 1. 推进下一步
        self._advance_next_step(state, step)
        # 2.返回None
        return None

    def _advance_next_step(self, state, step):
        # 1.寻找下一个stap_id
        next_step_id = self._select_next_step(step, state)
        # 2. 更新当前任务上下文的step_id(给当前执行任务流程的上下文用)不做这个动作，出不来
        state.current_active_task().step_id = next_step_id

    def _select_next_step(self, step: FlowStep, state: DialogueState) -> str:

        for link in step.next:
            if isinstance(link, StaticLink):
                return link.target  # 下一个步骤的id
            if isinstance(link, ConditionalLink):
                if self._eval_condition(state, link.condition):
                    return link.target
            if isinstance(link, FallbackLink):
                return link.target
        return "没有下一步"

    def _eval_condition(self, state: DialogueState, condition: str) -> bool:
        """判断下一个条件走那个步骤"""
        data = {
            "slots": state.active_task.slots,
            # current_active_task：获取当前任务上下文对象：系统任务优先
            # model_dump：对象转字典
            "context": state.current_active_task().model_dump(mode="json")
        }
        return bool(eval(condition, {'__builtins__': None}, data))



if __name__ == "__main__":
    import asyncio
    import uuid
    import time
    from pathlib import Path
    from task.flow.loader import FlowLoader
    from domain.state import DialogueState, Session
    from domain.contexts import TaskContext, CollectedSystemContext
    # 直接导入构建函数
    from task.action.builder import build_action_runner

    async def demo_recommend_goods():
        print("========= 1. 加载流程配置文件 =========")
        base = Path(__file__).parents[2]
        user_yml = base / "flow_config" / "user_flows.yml"
        sys_yml = base / "flow_config" / "system_flows.yml"

        loader = FlowLoader()
        flows = loader.load_many([user_yml, sys_yml])

        print("========= 2. 手动构建 DialogueState（推荐商品任务） =========")
        session = Session(
            session_id=str(uuid.uuid4()),
            started_at=time.time(),
            last_activity_at=time.time(),
            closed_at=None
        )
        # 流程id改为 recommend_similar_product，起始步骤 start，空槽位
        task_ctx = TaskContext(
            task_id=str(uuid.uuid4()),
            flow_id="recommend_similar_product",
            step_id="start",
            slots={}
        )
        session_state = DialogueState(
            sender_id="user_001",
            session=session,
            turns=[],
            active_task=task_ctx,
            paused_tasks=[],
            active_system_task=None,
            focused_object=None
        )

        print("\n========= 3. 一键构建完整 ActionRunner（自动注册全部动作） =========")
        runner = build_action_runner()
        executor = FlowExecutor()

        print("\n========= 4. 第一次推进流程：start 判断槽位 → 没有商品ID，询问用户商品 =========")
        messages1 = await executor.run_task(session_state, flows, runner)
        print("本轮机器人回复：", [bot.text for bot in messages1])

        print("\n========= 5. 模拟用户发送商品编号，写入槽位product_id =========")
        session_state.set_slots({"product_id": "P0001"})

        print("\n========= 6. 再次执行流程，执行推荐商品的action动作 =========")
        messages2 = await executor.run_task(session_state, flows, runner)
        print("本轮机器人回复：", [bot.text for bot in messages2])

        print("\n✅ 相似商品推荐流程执行结束")

    asyncio.run(demo_recommend_goods())




# if __name__ == "__main__":
#     import asyncio
#     import uuid
#     import time
#     from pathlib import Path
#     from task.flow.loader import FlowLoader
#     from domain.state import DialogueState, Session
#     from domain.contexts import TaskContext
#     # 直接导入构建函数
#     from task.action.builder import build_action_runner
#
#     async def demo():
#         print("========= 1. 加载流程配置文件 =========")
#         base = Path(__file__).parents[2]
#         user_yml = base / "flow_config" / "user_flows.yml"
#         sys_yml = base / "flow_config" / "system_flows.yml"
#
#         loader = FlowLoader()
#         flows = loader.load_many([user_yml, sys_yml])
#
#         print("========= 2. 手动构建 DialogueState =========")
#         session = Session(
#             session_id=str(uuid.uuid4()),
#             started_at=time.time(),
#             last_activity_at=time.time(),
#             closed_at=None
#         )
#         task_ctx = TaskContext(
#             task_id=str(uuid.uuid4()),
#             flow_id="refund_request",
#             step_id="start",
#             slots={}
#         )
#         session_state = DialogueState(
#             sender_id="user_001",
#             session=session,
#             turns=[],
#             active_task=task_ctx,
#             paused_tasks=[],
#             active_system_task=None,
#             focused_object=None
#         )
#
#         print("========= 3. 一键构建完整 ActionRunner（自动注册全部动作） =========")
#         runner = build_action_runner()
#         executor = FlowExecutor()
#
#         print("\n========= 4. 第一次推进流程：start → collect（询问订单号） =========")
#         messages1 = await executor.run_task(session_state, flows, runner)
#         print("本轮机器人回复：", [bot.text for bot in messages1])
#
#         print("\n========= 5. 模拟用户输入订单号，写入槽位 =========")
#         session_state.set_slots({"order_number": "OD999001"})
#
#         print("\n========= 6. 再次执行流程，收集退款原因 =========")
#         messages2 = await executor.run_task(session_state, flows, runner)
#         print("本轮机器人回复：", [bot.text for bot in messages2])
#
#         print("\n========= 7. 用户填入退款原因 =========")
#         session_state.set_slots({"refund_reason": "商品不满意"})
#
#         print("\n========= 8. 走完action_response、end节点 =========")
#         messages3 = await executor.run_task(session_state, flows, runner)
#         print("本轮机器人回复：", [bot.text for bot in messages3])
#
#         print("\n✅ 退款完整流程执行结束")
#
#     asyncio.run(demo())
