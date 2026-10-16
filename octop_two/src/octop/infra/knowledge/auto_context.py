"""Deterministic knowledge-base retrieval injected every chat turn.

Octop ships ``search_knowledge`` as an agentic tool: the model decides when to
call it. Weak models may skip the tool and answer from general knowledge while
claiming they searched ("基于我刚才的搜索结果"). This middleware removes the
reliance on model discretion: when knowledge bases are attached to the turn,
the system retrieves passages for the user's query and injects them into the
model request as a system message, every turn, before the first model call.

The ``search_knowledge`` tool stays available for follow-up queries the model
chooses to run on its own.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.config import get_config

from octop.infra.knowledge.retrieve import (
    _retrieve_context_sync,
    retrieve_context,
)

logger = logging.getLogger(__name__)

_AUTO_CONTEXT_NAME = "octop_knowledge_auto_context"

_AUTO_CONTEXT_NOTE_ZH = (
    "\n\n（系统提示：以上资料由系统在本轮自动检索注入，不是模型记忆。"
    "回答必须优先依据这些资料并标注来源；"
    "只有资料中确实没有答案时才可用通用知识补充，"
    "且必须先明确声明「知识库中未找到相关内容」，"
    "严禁把通用知识冒充为知识库内容。）"
    "\n\n（输出格式硬性要求："
    "直接输出与问题相关的最终答案，保持简洁；"
    "严禁叙述检索、浏览、查资料的过程，"
    "「让我查看」「现在让我访问」之类的过程描述一律禁止；"
    "若资料中没有答案，只回答一句「知识库中未找到相关内容」并简述问题，"
    "不得转而长篇上网检索考证。）"
)

_AUTO_CONTEXT_NOTE_EN = (
    "\n\n(System note: the passages above were retrieved automatically by the "
    "system for this turn, not recalled from memory. Ground your answer in "
    "them and cite sources. Only if they genuinely lack the answer may you "
    "add general knowledge, and you must first state that the knowledge "
    "bases contained no relevant content.)"
    "\n\n(Output format hard rules: give the final answer to the question "
    "directly and concisely; never narrate searching/browsing steps — "
    "phrases like \"let me check\" or \"now let me visit\" are forbidden. "
    "If the passages lack the answer, reply with one sentence stating the "
    "knowledge bases had no relevant content; do not fall back to lengthy "
    "web research.)"
)


def _cfg() -> dict[str, Any]:
    return get_config().get("configurable") or {}


def _selected_ids(cfg: dict[str, Any]) -> list[str]:
    raw = cfg.get("knowledge_base_ids")
    if not isinstance(raw, list):
        return []
    return [item.strip() for item in raw if isinstance(item, str) and item.strip()]


def _last_human_text(messages: Sequence[Any]) -> str:
    """Return the text of the most recent human message (this turn's query)."""
    for message in reversed(list(messages)):
        if isinstance(message, HumanMessage):
            content = message.content
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text") or ""))
                return "\n".join(parts).strip()
            return ""
    return ""


def _injection(context: str, locale: str) -> str:
    note = (
        _AUTO_CONTEXT_NOTE_ZH
        if str(locale).lower().startswith("zh")
        else _AUTO_CONTEXT_NOTE_EN
    )
    return context + note


def _should_skip(request: ModelRequest[Any], cfg: dict[str, Any]) -> bool:
    """Skip when: no human turn ending, no KBs, or no usable user identity."""
    messages = list(request.messages or [])
    if not messages or not isinstance(messages[-1], HumanMessage):
        # Only inject on the first model call of a turn; after tool calls the
        # trailing message is a ToolMessage and the context is already present.
        return True
    if not _selected_ids(cfg):
        return True
    return cfg.get("user") is None


class KnowledgeAutoContextMiddleware(AgentMiddleware[Any, Any]):
    """Inject retrieved knowledge-base passages into every chat turn."""

    def __init__(self, services: Any) -> None:
        self._services = services

    def _context_for_turn(
        self, request: ModelRequest[Any], cfg: dict[str, Any]
    ) -> str:
        query = _last_human_text(request.messages or [])
        if len(query) < 2:
            return ""
        return retrieve_context(
            self._services,
            user_id=int(cfg["user"]),
            is_admin=bool(cfg.get("user_is_admin")),
            query=query,
            knowledge_base_ids=_selected_ids(cfg),
            locale=str(cfg.get("locale") or "zh"),
        )

    def _injected_request(
        self, request: ModelRequest[Any], context: str, locale: str
    ) -> ModelRequest[Any]:
        messages = list(request.messages or [])
        injected = SystemMessage(
            name=_AUTO_CONTEXT_NAME,
            content=_injection(context, locale),
        )
        # Insert right before the human turn so the passages sit adjacent to
        # the question they answer.
        new_messages = messages[:-1] + [injected, messages[-1]]
        return request.override(messages=new_messages)

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        try:
            cfg = _cfg()
            if _should_skip(request, cfg):
                return handler(request)
            locale = str(cfg.get("locale") or "zh")
            context = _retrieve_context_sync(
                self._services,
                user_id=int(cfg["user"]),
                is_admin=bool(cfg.get("user_is_admin")),
                query=_last_human_text(request.messages or []),
                knowledge_base_ids=_selected_ids(cfg),
                k=8,
                char_budget=6000,
                locale=locale,
            )
            if not context:
                return handler(request)
            return handler(self._injected_request(request, context, locale))
        except Exception:
            logger.warning(
                "knowledge auto-context injection skipped", exc_info=True
            )
            return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        try:
            cfg = _cfg()
            if _should_skip(request, cfg):
                return await handler(request)
            locale = str(cfg.get("locale") or "zh")
            context = await self._context_for_turn(request, cfg)
            if not context:
                return await handler(request)
            return await handler(self._injected_request(request, context, locale))
        except Exception:
            logger.warning(
                "knowledge auto-context injection skipped", exc_info=True
            )
            return await handler(request)


__all__ = ["KnowledgeAutoContextMiddleware"]
