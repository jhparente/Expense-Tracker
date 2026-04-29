from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import Optional

# User Models
class UserRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True

# Expense Models
class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    date: date

class ExpenseUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = Field(None, max_length=500)
    date: Optional[date] = None

class ExpenseResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    category: str
    description: Optional[str]
    date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Summary Models
class CategorySummary(BaseModel):
    category: str
    total: float
    count: int

class ExpenseSummary(BaseModel):
    total_spent: float
    transaction_count: int
    categories: list[CategorySummary]

# Response Models
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class SuccessResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class ErrorResponse(BaseModel):
    success: bool
    error: str
    code: int
