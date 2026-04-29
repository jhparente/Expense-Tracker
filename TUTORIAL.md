# Expense Tracker - Full Documentation

A FastAPI-based expense tracking application with NeonDB (PostgreSQL) backend. Track, manage, and analyze your spending with a modern REST API.

## Features

- **FastAPI Backend**: High-performance async Python API
- **JWT Authentication**: Secure token-based authentication
- **Expense Management**: Full CRUD operations for expenses
- **Expense Categories**: Organize expenses by category
- **Summary Analytics**: Get spending summaries by category
- **NeonDB Integration**: Cloud-based PostgreSQL database
- **Auto Documentation**: Interactive API docs with Swagger UI
- **Type Safety**: Pydantic models for request/response validation

## Tech Stack

- **Backend**: Python 3.x, FastAPI, Uvicorn
- **Database**: NeonDB (PostgreSQL cloud)
- **Authentication**: JWT tokens with bcrypt password hashing
- **Validation**: Pydantic v2
- **Database Driver**: psycopg2

## Project Structure

```
Expense-Tracker/
├── app.py                 # FastAPI application with routes
├── models.py             # Pydantic request/response models
├── config.py             # Configuration and settings
├── db.py                 # Database connection and operations
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore           # Git ignore file
├── TUTORIAL.md          # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.8+
- pip (Python package manager)
- NeonDB account (get at [neon.tech](https://neon.tech))

### 2. Clone the Repository

```bash
git clone https://github.com/Bryan652/Expense-Tracker.git
cd Expense-Tracker
```

### 3. Create Virtual Environment

```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment

1. Get your NeonDB connection string from [neon.tech](https://neon.tech)
2. Create `.env` file:
   ```bash
   cp .env.example .env
   ```
3. Update `.env` with your credentials:
   ```
   DATABASE_URL=postgresql://user:password@ep-xxxxx.us-east-1.neon.tech/dbname?sslmode=require
   SECRET_KEY=your-secret-key-here-change-in-production
   ENVIRONMENT=development
   DEBUG=True
   ```

### 6. Run the Application

```bash
python app.py
```

Or with uvicorn directly:

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:

- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8000/redoc (ReDoc)

## API Endpoints

### Base URL

```
http://localhost:8000
```

### Authentication Endpoints

#### Register

```
POST /auth/register
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securepassword123"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "created_at": "2026-04-29T10:00:00"
  }
}
```

#### Login

```
POST /auth/login
Content-Type: application/json

{
  "email": "john@example.com",
  "password": "securepassword123"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": {...}
}
```

#### Get Current User

```
GET /auth/me
Authorization: Bearer <access_token>
```

### Expense Endpoints

#### Get All Expenses

```
GET /expenses
Authorization: Bearer <access_token>
```

#### Get Single Expense

```
GET /expenses/{expense_id}
Authorization: Bearer <access_token>
```

#### Create Expense

```
POST /expenses
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 25.50,
  "category": "Food",
  "date": "2026-04-29",
  "description": "Lunch at restaurant"
}
```

#### Update Expense

```
PUT /expenses/{expense_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "amount": 30.00,
  "category": "Food",
  "date": "2026-04-29",
  "description": "Updated description"
}
```

#### Delete Expense

```
DELETE /expenses/{expense_id}
Authorization: Bearer <access_token>
```

### Summary Endpoint

#### Get Expense Summary

```
GET /summary
Authorization: Bearer <access_token>

Response:
{
  "total_spent": 150.75,
  "transaction_count": 5,
  "categories": [
    {
      "category": "Food",
      "total": 75.50,
      "count": 3
    },
    {
      "category": "Transport",
      "total": 75.25,
      "count": 2
    }
  ]
}
```

## Usage Examples

### Using cURL

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"John","email":"john@example.com","password":"pass123"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"pass123"}'

# Get expenses (replace TOKEN with actual token)
curl -X GET http://localhost:8000/expenses \
  -H "Authorization: Bearer TOKEN"

# Create expense
curl -X POST http://localhost:8000/expenses \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 25.50,
    "category": "Food",
    "date": "2026-04-29",
    "description": "Lunch"
  }'
```

### Using Python requests

```python
import requests

BASE_URL = "http://localhost:8000"

# Register
response = requests.post(f"{BASE_URL}/auth/register", json={
    "name": "John Doe",
    "email": "john@example.com",
    "password": "pass123"
})
token = response.json()["access_token"]

# Create expense
headers = {"Authorization": f"Bearer {token}"}
response = requests.post(f"{BASE_URL}/expenses",
    headers=headers,
    json={
        "amount": 25.50,
        "category": "Food",
        "date": "2026-04-29",
        "description": "Lunch"
    }
)
```

## Environment Variables

```
# Database
DATABASE_URL=postgresql://user:password@ep-xxxxx.us-east-1.neon.tech/dbname?sslmode=require

# Security
SECRET_KEY=your-secret-key-here

# Environment
ENVIRONMENT=development
DEBUG=True
```

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Expenses Table

```sql
CREATE TABLE expenses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount DECIMAL(10, 2) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Security

- Passwords are hashed using bcrypt
- JWT tokens for stateless authentication
- SQL injection prevention with parameterized queries
- CORS enabled for frontend integration
- SSL database connections with NeonDB

## Troubleshooting

### Database Connection Error

- Verify DATABASE_URL in .env is correct
- Ensure NeonDB project is active
- Check internet connection for cloud database

### Import Errors

- Reinstall dependencies: `pip install -r requirements.txt`
- Verify virtual environment is activated

### Token Expired

- Get a new token by logging in again
- Default token expiry: 24 hours

## Future Enhancements

- [ ] Refresh token functionality
- [ ] Advanced filtering and search
- [ ] Recurring expenses
- [ ] Budget limits
- [ ] Email notifications
- [ ] Mobile app
- [ ] WebSocket for real-time updates
- [ ] Expense export (CSV, PDF)

## License

School project - 2026

## Author

Bryan652
