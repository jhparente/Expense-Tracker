import psycopg
from psycopg.rows import dict_row
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

class Database:
    def __init__(self, database_url):
        self.database_url = database_url
        self.connection = None

    def connect(self):
        """Establish connection to NeonDB"""
        try:
            self.connection = psycopg.connect(self.database_url, row_factory=dict_row)
            print("✓ Connected to NeonDB")
        except (Exception, psycopg.Error) as error:
            print(f"✗ Error connecting to NeonDB: {error}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            print("✓ Disconnected from NeonDB")

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                results = cursor.fetchall()
                return results if results else []
        except (Exception, psycopg.Error) as error:
            print(f"✗ Query error: {error}")
            raise

    def execute_update(self, query: str, params: tuple = None) -> int:
        """Execute INSERT, UPDATE, or DELETE query"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                rows_affected = cursor.rowcount
            self.connection.commit()
            return rows_affected
        except (Exception, psycopg.Error) as error:
            self.connection.rollback()
            print(f"✗ Update error: {error}")
            raise

    def execute_insert_with_return(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Execute INSERT query and return the created row"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params or ())
                result = cursor.fetchone()
            self.connection.commit()
            return result
        except (Exception, psycopg.Error) as error:
            self.connection.rollback()
            print(f"✗ Insert error: {error}")
            raise

    def init_db(self):
        """Initialize database schema"""
        if not self.connection:
            self.connect()

        create_users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        create_expenses_table = """
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount DECIMAL(10, 2) NOT NULL,
            category VARCHAR(50) NOT NULL,
            description TEXT,
            date DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """

        try:
            cursor = self.connection.cursor()
            cursor.execute(create_users_table)
            cursor.execute(create_expenses_table)
            self.connection.commit()
            cursor.close()
            print("✓ Database schema initialized")
        except (Exception, psycopg.Error) as error:
            self.connection.rollback()
            print(f"✗ Error initializing schema: {error}")
            raise

    # User operations
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        query = "SELECT * FROM users WHERE email = %s"
        results = self.execute_query(query, (email,))
        return results[0] if results else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        query = "SELECT id, name, email, created_at FROM users WHERE id = %s"
        results = self.execute_query(query, (user_id,))
        return results[0] if results else None

    def create_user(self, name: str, email: str, hashed_password: str) -> Dict[str, Any]:
        """Create new user and return the user data"""
        query = """
        INSERT INTO users (name, email, password) 
        VALUES (%s, %s, %s)
        RETURNING id, name, email, created_at
        """
        return self.execute_insert_with_return(query, (name, email, hashed_password))

    # Expense operations
    def get_expenses(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all expenses for a user"""
        query = "SELECT * FROM expenses WHERE user_id = %s ORDER BY date DESC"
        return self.execute_query(query, (user_id,))

    def get_expense_by_id(self, expense_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Get specific expense by ID (verify ownership)"""
        query = "SELECT * FROM expenses WHERE id = %s AND user_id = %s"
        results = self.execute_query(query, (expense_id, user_id))
        return results[0] if results else None

    def create_expense(self, user_id: int, amount: float, category: str, 
                      description: str, date: str) -> Dict[str, Any]:
        """Create new expense and return the expense data"""
        query = """
        INSERT INTO expenses (user_id, amount, category, description, date) 
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """
        return self.execute_insert_with_return(query, (user_id, amount, category, description, date))

    def update_expense(self, expense_id: int, user_id: int, 
                      amount: float = None, category: str = None, 
                      description: str = None, date: str = None) -> bool:
        """Update expense (verify ownership)"""
        # Build dynamic UPDATE query
        updates = []
        params = []
        
        if amount is not None:
            updates.append("amount = %s")
            params.append(amount)
        if category is not None:
            updates.append("category = %s")
            params.append(category)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if date is not None:
            updates.append("date = %s")
            params.append(date)
        
        if not updates:
            return False
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([expense_id, user_id])
        
        query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = %s AND user_id = %s"
        return self.execute_update(query, tuple(params)) > 0

    def delete_expense(self, expense_id: int, user_id: int) -> bool:
        """Delete expense (verify ownership)"""
        query = "DELETE FROM expenses WHERE id = %s AND user_id = %s"
        return self.execute_update(query, (expense_id, user_id)) > 0

    def get_expense_summary(self, user_id: int) -> List[Dict[str, Any]]:
        """Get expense summary by category"""
        query = """
        SELECT 
            category, 
            SUM(amount)::float as total, 
            COUNT(*) as count
        FROM expenses 
        WHERE user_id = %s 
        GROUP BY category
        ORDER BY total DESC
        """
        return self.execute_query(query, (user_id,))

    def get_total_spent(self, user_id: int) -> float:
        """Get total spent by user"""
        query = "SELECT COALESCE(SUM(amount), 0)::float as total FROM expenses WHERE user_id = %s"
        results = self.execute_query(query, (user_id,))
        return results[0]['total'] if results else 0.0

# Initialize global database instance
db = Database(os.getenv('DATABASE_URL'))

