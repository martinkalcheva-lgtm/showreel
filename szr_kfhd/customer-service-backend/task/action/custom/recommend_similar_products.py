# itwwy/task/action/custom/recommend_similar_products.py
from typing import Any

from task.action.base import ActionResult
from task.action.base import Action
from domain.state import DialogueState
from task.action.custom.shared import fetch_product
from domain.messages import BotMessage


class RecommendSimilarProductsAction(Action):
    name = "action_recommend_similar_products"

    async def run(self, state: DialogueState, action_kwargs: dict[str, Any]) -> ActionResult:
        product_id = state.active_task.slots.get("product_id")
        label = product_id or "这件商品"

        payload = await fetch_product(product_id)
        if payload:
            label = str(payload.get("title") or "").strip() or label

        text = (
            f"我已经收到你对\"{label}\"的相似商品推荐需求。"
            "不过当前版本还没有接入正式的推荐系统，稍后可以继续补上这部分能力。"
        )
        bot_msg = BotMessage(text=text)
        return ActionResult(messages=[bot_msg])