from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    role: str = Field(index=True)  # "user" or "merchant"
    green_points: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TransactionCode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    merchant_id: int = Field(index=True)
    points: int
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
