# 所有表模型都继承它 SQLAlchemy 才能统一管理它们的元数据。
from mymodels.base import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import TEXT

class DialogueStateRecord(Base):
    __tablename__ = "dialogue_states"
    sender_id:Mapped[str]=mapped_column(primary_key=True)
    # 数据库长文本类型
    state_json: Mapped[str] = mapped_column(TEXT, nullable=False, default={})

