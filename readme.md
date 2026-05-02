# Jimwels Expense Tracker

## Setup Instructions

1. Copy environment file

   ```bash
   cp .env.example .env
   ```

2. Add database URL to `.env`

   ```
   DATABASE_URL=your_neon_db_connection_string
   ```

3. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

4. To run
   '''bash
   python app.py
   '''

## Endpoints

### Access Swagger Documentation

```
http://localhost:8000/docs#/
```

### View Database Tables

Go to NeonDB console to see all table changes in real-time.

---

## Authentication Flow

### 1. Register User

- POST `/auth/register` in Swagger
- Response includes `access_token` (example):
  ```
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9eyJzdWIiOiIyIiwiZXhwIjoxNzc3ODE5NjY0fQxsUKjLObhMNhojiNWyTuVnyrMmLxysbGeqlwCnhM78M
  ```

### 2. Authenticate

- Copy the `access_token` from response
- Click the **lock icon** in Swagger
- Paste the token

### 3. Login

- Same process as registration (POST `/auth/login`)

### 4. Access User Expenses

- Once authenticated, all endpoints are available
- Retrieve all expenses for the logged-in user
- All operations are linked to the authenticated user
