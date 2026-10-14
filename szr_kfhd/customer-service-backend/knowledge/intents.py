# 知识意图
"""
比如 :
这件衣服什么材质？  -> `product_info`（商品信息咨询）
我的订单啥状态了？  -> `order_info`（订单信息咨询）
退款多久到账？     -> `refund_policy`（退款政策咨询）
支持七天无理由吗？  -> `return_policy`（退货政策咨询）
你们多久发货？     -> `shipping_policy`（配送政策咨询）
"""

from pydantic import BaseModel


class KnowledgeIntent(BaseModel):
    id: str
    description: str
    # 这个意图要查哪些知识源（FAQ、RAG、订单 API 等）
    provider_ids: list[str] = []
    # 这个意图是否必须依附一个聚焦对象
    requires_object: str | None = None

KNOWLEDGE_INTENTS: dict[str, KnowledgeIntent] = {
    "product_info": KnowledgeIntent(
        id="product_info",
        description="商品信息咨询",
        provider_ids=["api.product"],
        requires_object="product",
    ),
    "order_info": KnowledgeIntent(
        id="order_info",
        description="订单信息咨询",
        provider_ids=["api.order"],
        requires_object="order",
    ),
    "refund_policy": KnowledgeIntent(
        id="refund_policy",
        description="退款政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    "return_policy": KnowledgeIntent(
        id="return_policy",
        description="退货政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    "shipping_policy": KnowledgeIntent(
        id="shipping_policy",
        description="配送政策咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
    "platform_rule": KnowledgeIntent(
        id="platform_rule",
        description="平台规则咨询",
        provider_ids=["rag.default"],
    ),
    "general_ecommerce_info": KnowledgeIntent(
        id="general_ecommerce_info",
        description="电商通用信息咨询",
        provider_ids=["faq.default", "rag.default"],
    ),
}