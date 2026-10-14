# itwwy/knowledge/providers.py

import json, asyncio
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from conf.config import settings
from domain.state import DialogueState
from infrastructure import http_client


class KnowledgeChunk(BaseModel):
    content: str

class KnowledgeProvider(ABC):

    # 知识提者的ID
    provider_id = ""

    @abstractmethod
    async def retrieve(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        提供检索方法
        :param state:
        :return:
        """
        pass

class ProductAPIProvider(KnowledgeProvider):
    provider_id = 'api.product' # 服务商id

    async def retrieve(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
            先拿到 聚焦对象的id -> 拿到这个聚焦卡片的信息 -> 转为json格式
            :return 商品信息
        """
        product_id = state.focused_object.id
        data: dict[str, Any] = await self._get_product_info_by_id(product_id)
        text = json.dumps(data, ensure_ascii=False, indent=2)
        return [KnowledgeChunk(content=f"商品信息:\n{text}")]

    async def _get_product_info_by_id(self, product_id: str) -> dict[str, Any]:
        url = f"{settings.commerce_api_base_url}/products/{product_id}"
        # 注意此处：
        # 文件头部 from infrastructure import http_client
        # 此处使用 http_client.http_client.get(url) 调用

        # 不要这样做：
        # 文件头部 from itwwy.infrastructure.http_client import http_client
        # 此处使用 http_client.get(url) 调用
        # 会使拿到的 http_client 是 None
        response = await http_client.http_client.get(url)
        return response.json()["data"]

class OrderAPIProvider(KnowledgeProvider):

    provider_id = 'api.order'

    async def retrieve(self, state: DialogueState) -> list[KnowledgeChunk]:
        """
        请求业务后端拿到 订单信息 和 物流信息
        :return 订单号，订单信息，物流信息
        """
        order_number = state.focused_object.id

        order_payload, logistics_payload = await asyncio.gather(
            self._fetch_order(order_number),
            self._fetch_logistics(order_number),
        )

        return [
            KnowledgeChunk(
                content="订单与物流信息：\n"
                        + json.dumps(
                    {
                        "order_number": order_number,
                        "order": order_payload,
                        "logistics": logistics_payload,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        ]

    async def _fetch_order(self, order_number) -> dict[str, Any]:
        url = f"{settings.commerce_api_base_url}/orders/{order_number}"
        response = await http_client.http_client.get(url)
        return response.json()["data"]

    async def _fetch_logistics(self, order_number) -> dict[str, Any]:
        url = f"{settings.commerce_api_base_url}/orders/{order_number}/logistics"
        response = await http_client.http_client.get(url)
        return response.json().get("data", {})

class FAQProvider(KnowledgeProvider):

    provider_id = 'faq.default'

    async def retrieve(self, state: DialogueState) -> list[KnowledgeChunk]:
        # TODO
        return [KnowledgeChunk(content="FAQ：未检索到相关问题")]

class RAGProvider(KnowledgeProvider):
    """检索相关商品"""

    provider_id = 'rag.default'

    async def retrieve(self, state: DialogueState) -> list[KnowledgeChunk]:
        # TODO
        return [KnowledgeChunk(content="RAG：未检索到相关信息")]
