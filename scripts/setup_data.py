"""Setup sample data for MCP servers."""

import asyncio
import aiosqlite
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings


async def setup_sample_database():
    """Create sample SQLite database with test data."""
    settings = get_settings()
    db_path = Path(settings.database_path)
    
    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database if it exists
    if db_path.exists():
        db_path.unlink()
    
    async with aiosqlite.connect(str(db_path)) as db:
        # Create sample tables
        await db.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                age INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                category TEXT,
                stock INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.execute("""
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total_price REAL NOT NULL,
                order_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        
        # Insert sample data
        await db.execute("""
            INSERT INTO users (name, email, age) VALUES
            ('Alice Johnson', 'alice@example.com', 30),
            ('Bob Smith', 'bob@example.com', 25),
            ('Charlie Brown', 'charlie@example.com', 35),
            ('Diana Prince', 'diana@example.com', 28)
        """)
        
        await db.execute("""
            INSERT INTO products (name, description, price, category, stock) VALUES
            ('Laptop', 'High-performance laptop', 999.99, 'Electronics', 10),
            ('Mouse', 'Wireless mouse', 29.99, 'Electronics', 50),
            ('Keyboard', 'Mechanical keyboard', 79.99, 'Electronics', 30),
            ('Monitor', '27-inch 4K monitor', 399.99, 'Electronics', 15),
            ('Headphones', 'Noise-cancelling headphones', 199.99, 'Electronics', 20)
        """)
        
        await db.execute("""
            INSERT INTO orders (user_id, product_id, quantity, total_price) VALUES
            (1, 1, 1, 999.99),
            (1, 2, 2, 59.98),
            (2, 3, 1, 79.99),
            (3, 4, 1, 399.99),
            (4, 5, 1, 199.99)
        """)
        
        await db.commit()
        print(f"[OK] Sample database created at: {db_path}")
        print("   - Created tables: users, products, orders")
        print("   - Inserted sample data")


async def main():
    """Main function."""
    print("Setting up sample data for MCP servers...")
    await setup_sample_database()
    print("[OK] Setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
