"""SQLite database operations for catalog server."""

import aiosqlite
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import get_settings


class CatalogDatabase:
    """Database operations for catalog server."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize catalog database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.settings = get_settings()
        self.db_path = db_path or self.settings.database_path
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def list_tables(self) -> List[str]:
        """List all tables in the database.
        
        Returns:
            List of table names
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            rows = await cursor.fetchall()
            return [row[0] for row in rows]
    
    async def describe_table(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Dictionary with table schema information
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Get table info
            cursor = await db.execute(
                f"PRAGMA table_info({table_name})"
            )
            columns = await cursor.fetchall()
            
            # Get column details
            column_info = []
            for col in columns:
                column_info.append({
                    "name": col[1],
                    "type": col[2],
                    "not_null": bool(col[3]),
                    "default_value": col[4],
                    "primary_key": bool(col[5])
                })
            
            return {
                "table_name": table_name,
                "columns": column_info
            }
    
    async def get_table_row_count(self, table_name: str) -> int:
        """Get the number of rows in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Number of r ows
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name}")
            row = await cursor.fetchone()
            return row[0] if row else 0
