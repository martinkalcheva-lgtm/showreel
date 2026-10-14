# task/action/base.py

from abc import ABC, abstractmethod
from typing import Any
from domain.state import DialogueState
from domain.messages import BotMessage
from pydantic import BaseModel


class Action(ABC):
    """ 所有动作的基类 """
    name: str  # Action名字

    @abstractmethod
    async def run(self,
                  state: DialogueState,
                  action_kwargs: dict[str, Any]
                  ):
        pass


class ActionResult(BaseModel):
    """ 动作统一格式的返回数据包 """
    messages: list[BotMessage] = []  # 要发给用户的消息
    slot_updates: dict[str, Any] = {}  # 要写回 state 的槽位


