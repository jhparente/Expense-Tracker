from fastapi import FastAPI, Depends, HTTPException, Request, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional
import time
import jwt
import bcrypt
from db import db
from config import settings
from models import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    CategorySummary, ExpenseSummary, PeriodSummary,
    CategoryCreate, CategoryResponse
)

# Initialize FastAPI app
app = FastAPI(
    title="Expense Tracker API",
    description="A FastAPI backend for expense tracking with NeonDB",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security setup
security = HTTPBearer()

# Simple in-memory rate limiting (per IP)
RATE_LIMITS = {
    "register": (3, 60),
    "expense_write": (30, 60),
}
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)

LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 30
_login_failures: dict[str, dict[str, float]] = {}


def rate_limit(key: str, limit: int, window_seconds: int):
    async def dependency(request: Request):
        client_host = request.client.host if request.client else "unknown"
        now = time.time()
        bucket_key = f"{key}:{client_host}"
        bucket = _rate_buckets[bucket_key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)

    return dependency

def _login_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{email.lower()}"

def _get_lockout_remaining(key: str) -> int | None:
    record = _login_failures.get(key)
    if not record:
        return None
    now = time.time()
    locked_until = record.get("locked_until", 0.0)
    if locked_until > now:
        return max(1, int(locked_until - now))
    return None

def _record_login_failure(key: str) -> int | None:
    now = time.time()
    record = _login_failures.get(key, {"count": 0, "locked_until": 0.0})
    if record.get("locked_until", 0.0) > now:
        return max(1, int(record["locked_until"] - now))
    record["count"] = record.get("count", 0) + 1
    if record["count"] >= LOGIN_MAX_ATTEMPTS:
        record["count"] = 0
        record["locked_until"] = now + LOGIN_LOCKOUT_SECONDS
        _login_failures[key] = record
        return LOGIN_LOCKOUT_SECONDS
    _login_failures[key] = record
    return None

# Initialize database
@app.on_event("startup")
def startup():
    """Initialize database on startup"""
    try:
        db.connect()
        db.init_db()
        print("✓ Application started successfully")
    except Exception as e:
        print(f"✗ Startup error: {e}")
        raise

@app.on_event("shutdown")
def shutdown():
    """Cleanup on shutdown"""
    db.disconnect()
    print("✓ Application shutdown")

# Utility functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

def normalize_category(name: str) -> str:
    """Normalize category names to avoid duplicates with extra whitespace."""
    return " ".join(name.strip().split())

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {"sub": str(user_id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(credentials = Depends(security)) -> int:
    """Verify JWT token and return user_id"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return int(user_id)
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "database": "connected"
    }

# Create API router
api_router = APIRouter(prefix="/api/v1")

# ============= Authentication Routes =============

@api_router.post(
    "/auth/register",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("register", *RATE_LIMITS["register"]))],
)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = db.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Create user
        user = db.create_user(user_data.name, user_data.email, hashed_password)
        
        # Create token
        access_token = create_access_token(user['id'])
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(**user)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@api_router.post(
    "/auth/login",
    response_model=TokenResponse,
)
async def login(credentials: UserLogin, request: Request):
    """Login user and return access token"""
    try:
        lockout_key = _login_key(request, credentials.email)
        remaining = _get_lockout_remaining(lockout_key)
        if remaining is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Try again in {remaining}s.",
                headers={"Retry-After": str(remaining)},
            )
        # Get user by email
        user = db.get_user_by_email(credentials.email)
        if not user:
            remaining = _record_login_failure(lockout_key)
            if remaining is not None:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {remaining}s.",
                    headers={"Retry-After": str(remaining)},
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(credentials.password, user['password']):
            remaining = _record_login_failure(lockout_key)
            if remaining is not None:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Try again in {remaining}s.",
                    headers={"Retry-After": str(remaining)},
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if lockout_key in _login_failures:
            del _login_failures[lockout_key]
        
        # Create token
        access_token = create_access_token(user['id'])
        
        # Return user info without password
        user_response = UserResponse(**{
            'id': user['id'],
            'name': user['name'],
            'email': user['email'],
            'created_at': user['created_at']
        })
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@api_router.get("/auth/me", response_model=UserResponse)
async def get_current_user(user_id: int = Depends(verify_token)):
    """Get current authenticated user"""
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return UserResponse(**user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user: {str(e)}"
        )

# ============= Category Routes =============

@api_router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(user_id: int = Depends(verify_token)):
    """List categories for the authenticated user"""
    try:
        categories = db.get_categories(user_id)
        return [CategoryResponse(**cat) for cat in categories]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching categories: {str(e)}"
        )

@api_router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("expense_write", *RATE_LIMITS["expense_write"]))],
)
async def create_category(category: CategoryCreate, user_id: int = Depends(verify_token)):
    """Create a category for the authenticated user"""
    try:
        name = normalize_category(category.name)
        if not name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name is required"
            )
        existing = db.get_category_by_name(user_id, name)
        if existing:
            return CategoryResponse(**existing)
        created = db.create_category(user_id, name)
        return CategoryResponse(**created)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating category: {str(e)}"
        )

# ============= Expense Routes =============

@api_router.get("/expenses", response_model=list[ExpenseResponse])
async def get_expenses(user_id: int = Depends(verify_token)):
    """Get all expenses for the authenticated user"""
    try:
        expenses = db.get_expenses(user_id)
        return [ExpenseResponse(**expense) for expense in expenses]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching expenses: {str(e)}"
        )

@api_router.get("/expenses/{expense_id}", response_model=ExpenseResponse)
async def get_expense(expense_id: int, user_id: int = Depends(verify_token)):
    """Get a specific expense"""
    try:
        expense = db.get_expense_by_id(expense_id, user_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        return ExpenseResponse(**expense)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching expense: {str(e)}"
        )

@api_router.post(
    "/expenses",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("expense_write", *RATE_LIMITS["expense_write"]))],
)
async def create_expense(expense_data: ExpenseCreate, user_id: int = Depends(verify_token)):
    """Create a new expense"""
    try:
        category_name = normalize_category(expense_data.category)
        if not category_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category is required"
            )
        db.ensure_category(user_id, category_name)
        expense = db.create_expense(
            user_id=user_id,
            amount=expense_data.amount,
            category=category_name,
            description=expense_data.description or "",
            date=expense_data.date.isoformat()
        )
        return ExpenseResponse(**expense)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating expense: {str(e)}"
        )

@api_router.put(
    "/expenses/{expense_id}",
    response_model=ExpenseResponse,
    dependencies=[Depends(rate_limit("expense_write", *RATE_LIMITS["expense_write"]))],
)
async def update_expense(
    expense_id: int,
    expense_data: ExpenseUpdate,
    user_id: int = Depends(verify_token)
):
    """Update an expense"""
    try:
        # Check if expense exists and belongs to user
        expense = db.get_expense_by_id(expense_id, user_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Update expense
        category_name = None
        if expense_data.category is not None:
            category_name = normalize_category(expense_data.category)
            if not category_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category is required"
                )
            db.ensure_category(user_id, category_name)

        success = db.update_expense(
            expense_id=expense_id,
            user_id=user_id,
            amount=expense_data.amount,
            category=category_name,
            description=expense_data.description,
            date=expense_data.date.isoformat() if expense_data.date else None
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update expense"
            )
        
        # Return updated expense
        updated_expense = db.get_expense_by_id(expense_id, user_id)
        return ExpenseResponse(**updated_expense)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating expense: {str(e)}"
        )

@api_router.delete(
    "/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("expense_write", *RATE_LIMITS["expense_write"]))],
)
async def delete_expense(expense_id: int, user_id: int = Depends(verify_token)):
    """Delete an expense"""
    try:
        # Check if expense exists and belongs to user
        expense = db.get_expense_by_id(expense_id, user_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Delete expense
        success = db.delete_expense(expense_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to delete expense"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting expense: {str(e)}"
        )

# ============= Summary Routes =============

@api_router.get("/summary", response_model=ExpenseSummary)
async def get_summary(user_id: int = Depends(verify_token)):
    """Get expense summary for the authenticated user"""
    try:
        # Get category summary
        categories = db.get_expense_summary(user_id)
        category_list = [
            CategorySummary(
                category=cat['category'],
                total=float(cat['total']),
                count=int(cat['count'])
            )
            for cat in categories
        ]
        
        # Get total spent
        total_spent = db.get_total_spent(user_id)
        
        # Count transactions
        expenses = db.get_expenses(user_id)
        transaction_count = len(expenses)
        
        return ExpenseSummary(
            total_spent=total_spent,
            transaction_count=transaction_count,
            categories=category_list
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching summary: {str(e)}"
        )

@api_router.get("/summary/periods", response_model=PeriodSummary)
async def get_period_summary(user_id: int = Depends(verify_token)):
    """Get total spent for day, week, and month"""
    try:
        today = datetime.now().date()
        week_start = today - timedelta(days=6)
        month_start = today.replace(day=1)

        day_total = db.get_total_spent_between(user_id, today, today)
        week_total = db.get_total_spent_between(user_id, week_start, today)
        month_total = db.get_total_spent_between(user_id, month_start, today)

        return PeriodSummary(
            day_total=day_total,
            week_total=week_total,
            month_total=month_total,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching period summary: {str(e)}"
        )

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Expense Tracker API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "auth": {
            "register": "POST /auth/register",
            "login": "POST /auth/login",
            "current_user": "GET /auth/me"
        },
        "resources": {
            "categories": "GET /categories",
            "create_category": "POST /categories",
            "expenses": "GET /expenses",
            "expense_detail": "GET /expenses/{id}",
            "create_expense": "POST /expenses",
            "update_expense": "PUT /expenses/{id}",
            "delete_expense": "DELETE /expenses/{id}",
            "summary": "GET /summary",
            "summary_periods": "GET /summary/periods"
        }
    }

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
