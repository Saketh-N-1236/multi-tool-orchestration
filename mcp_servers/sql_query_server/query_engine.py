"""SQL query engine with read-only enforcement."""

import aiosqlite
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import get_settings


# Read-only SQL keywords
READ_ONLY_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "REPLACE", "GRANT", "REVOKE", "COMMIT", "ROLLBACK"
]


def validate_read_only(query: str) -> None:
    """Validate that query is read-only.
    
    Args:
        query: SQL query string
        
    Raises:
        ValueError: If query contains write operations
    """
    query_upper = query.upper().strip()
    
    # Check for read-only keywords
    for keyword in READ_ONLY_KEYWORDS:
        if query_upper.startswith(keyword):
            raise ValueError(
                f"Read-only mode: {keyword} operations are not allowed. "
                f"Only SELECT queries are permitted."
            )
    
    # Additional check: ensure it's a SELECT query
    if not query_upper.startswith("SELECT"):
        raise ValueError(
            "Read-only mode: Only SELECT queries are allowed. "
            f"Query starts with: {query_upper.split()[0] if query_upper.split() else 'empty'}"
        )


class SQLQueryEngine:
    """SQL query engine with read-only enforcement."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize SQL query engine.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.settings = get_settings()
        self.db_path = db_path or self.settings.database_path
    
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute a read-only SQL query.
        
        Args:
            query: SQL SELECT query
            
        Returns:
            Dictionary with query results
            
        Raises:
            ValueError: If query is not read-only
        """
        # Validate read-only
        validate_read_only(query)
        
        async with aiosqlite.connect(self.db_path) as db:
            # Enable row factory for dict-like access
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            
            # Convert rows to list of dictionaries
            results = [dict(row) for row in rows]
            
            return {
                "query": query,
                "row_count": len(results),
                "results": results
            }
    
    async def explain_query(self, query: str) -> Dict[str, Any]:
        """Get query execution plan (EXPLAIN QUERY PLAN).
        
        Args:
            query: SQL SELECT query
            
        Returns:
            Dictionary with execution plan
        """
        # Validate read-only
        validate_read_only(query)
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"EXPLAIN QUERY PLAN {query}")
            plan = await cursor.fetchall()
            
            return {
                "query": query,
                "execution_plan": [dict(row) for row in plan]
            }
