from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from db import db
from config import settings
from models import (
    UserRegister, UserLogin, UserResponse, TokenResponse,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse,
    CategorySummary, ExpenseSummary
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

# ============= Authentication Routes =============

@app.post("/auth/register", response_model=TokenResponse)
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

@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login user and return access token"""
    try:
        # Get user by email
        user = db.get_user_by_email(credentials.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(credentials.password, user['password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
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

@app.get("/auth/me", response_model=UserResponse)
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

# ============= Expense Routes =============

@app.get("/expenses", response_model=list[ExpenseResponse])
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

@app.get("/expenses/{expense_id}", response_model=ExpenseResponse)
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

@app.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(expense_data: ExpenseCreate, user_id: int = Depends(verify_token)):
    """Create a new expense"""
    try:
        expense = db.create_expense(
            user_id=user_id,
            amount=expense_data.amount,
            category=expense_data.category,
            description=expense_data.description or "",
            date=expense_data.date.isoformat()
        )
        return ExpenseResponse(**expense)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating expense: {str(e)}"
        )

@app.put("/expenses/{expense_id}", response_model=ExpenseResponse)
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
        success = db.update_expense(
            expense_id=expense_id,
            user_id=user_id,
            amount=expense_data.amount,
            category=expense_data.category,
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

@app.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
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

@app.get("/summary", response_model=ExpenseSummary)
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
            "expenses": "GET /expenses",
            "expense_detail": "GET /expenses/{id}",
            "create_expense": "POST /expenses",
            "update_expense": "PUT /expenses/{id}",
            "delete_expense": "DELETE /expenses/{id}",
            "summary": "GET /summary"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
