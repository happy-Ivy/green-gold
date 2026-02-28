from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    role: str = Field(index=True)  # "user" or "merchant" or "admin"
    green_points: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TransactionCode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    # 6 碼：前三碼英文(隨機) + 後三碼點數(左補0)
    code: str = Field(index=True, unique=True)

    # 代碼由哪個店家產生
    merchant_id: int = Field(index=True)

    # 幾點（0~999）
    points: int = Field(default=0)

    # 是否已被兌換
    is_used: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    used_at: Optional[datetime] = None
    used_by_user_id: Optional[int] = Field(default=None, index=True)


class PointLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    merchant_id: int = Field(index=True)
    points: int
    code: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)