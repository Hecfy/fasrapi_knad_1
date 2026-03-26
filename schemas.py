from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    login: str = Field(..., min_length=3, max_length=50)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)

class UserOut(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    status: str = Field(default="pending")
    priority: int = Field(default=1, ge=1, le=5)

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)

class TaskOut(TaskBase):
    id: int
    created_at: datetime
    owner_id: int
    model_config = ConfigDict(from_attributes=True)

class TasksList(BaseModel):
    tasks: List[TaskOut]
    total: int