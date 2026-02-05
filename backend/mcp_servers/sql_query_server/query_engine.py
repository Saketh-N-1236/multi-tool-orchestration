"""SQL query engine with read-only enforcement."""

import aiosqlite
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import get_settings
from mcp_servers.catalog_server.catalog_manager import CatalogManager


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
    if not query or not query.strip():
        raise ValueError("Empty query is not allowed")
    
    query_upper = query.upper().strip()
    
    # Remove string literals first (to avoid false positives)
    # Replace string literals with placeholders
    string_pattern = r"(['\"])(?:(?=(\\?))\2.)*?\1"
    string_placeholders = []
    def replace_string(match):
        placeholder = f"__STRING_{len(string_placeholders)}__"
        string_placeholders.append(match.group(0))
        return placeholder
    query_no_strings = re.sub(string_pattern, replace_string, query_upper)
    
    # Remove comments and normalize whitespace for better detection
    # Remove single-line comments (-- comment)
    query_clean = '\n'.join(line.split('--')[0] for line in query_no_strings.split('\n'))
    # Remove multi-line comments (/* comment */)
    query_clean = re.sub(r'/\*.*?\*/', '', query_clean, flags=re.DOTALL)
    # Normalize whitespace
    query_clean = ' '.join(query_clean.split())
    
    # Check for read-only keywords anywhere in the query (not just start)
    # This prevents injection attempts like "SELECT * FROM users; DROP TABLE users;"
    # Note: We check after removing comments, so keywords in comments won't trigger
    for keyword in READ_ONLY_KEYWORDS:
        # Check if keyword appears as a standalone word (not part of another word)
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, query_clean):
            raise ValueError(
                f"Read-only mode: {keyword} operations are not allowed. "
                f"Only SELECT queries are permitted."
            )
    
    # Additional check: ensure it starts with SELECT
    if not query_clean.startswith("SELECT"):
        raise ValueError(
            "Read-only mode: Only SELECT queries are allowed. "
            f"Query starts with: {query_clean.split()[0] if query_clean.split() else 'empty'}"
        )
    
    # Check for semicolons that might indicate multiple statements
    # Allow semicolon at the end (common in SQL), but not in the middle
    if ';' in query_clean[:-1]:  # Check all but the last character
        raise ValueError(
            "Read-only mode: Multiple statements are not allowed. "
            "Only single SELECT queries are permitted."
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
        self._catalog_manager = None
    
    def _get_catalog_manager(self) -> CatalogManager:
        """Get or create catalog manager instance."""
        if self._catalog_manager is None:
            self._catalog_manager = CatalogManager()
        return self._catalog_manager
    
    def _resolve_database_path(self, database: Optional[str] = None) -> str:
        """Resolve database path from catalog name or use default.
        
        Args:
            database: Optional catalog/database name. If None, uses default database.
            
        Returns:
            Path to SQLite database file
            
        Raises:
            ValueError: If database name is provided but not found in catalogs
        """
        if database is None:
            # Use default database
            return self.db_path
        
        # Get database path from catalog manager
        catalog_manager = self._get_catalog_manager()
        
        # Check if catalog exists, if not try to discover it from file system
        if database not in catalog_manager.catalogs:
            # Try to discover it by checking file system
            data_dir = Path(self.settings.database_path).parent
            db_file = data_dir / f"{database}.db"
            if db_file.exists():
                catalog_manager.catalogs[database] = {
                    "type": "sqlite",
                    "path": str(db_file)
                }
            else:
                # List available catalogs for better error message
                available = list(catalog_manager.catalogs.keys())
                raise ValueError(
                    f"Database '{database}' not found. "
                    f"Available databases: {', '.join(available) if available else 'none'}. "
                    f"File '{db_file}' does not exist."
                )
        
        catalog_config = catalog_manager.catalogs[database]
        if catalog_config["type"] != "sqlite":
            raise ValueError(f"Database type '{catalog_config['type']}' not supported. Only SQLite databases are supported.")
        
        return catalog_config["path"]
    
    async def execute_query(self, query: str, database: Optional[str] = None) -> Dict[str, Any]:
        """Execute a read-only SQL query.
        
        Args:
            query: SQL SELECT query
            database: Optional database/catalog name. If None, uses default database.
            
        Returns:
            Dictionary with query results including database information
            
        Raises:
            ValueError: If query is not read-only or database not found
        """
        # Validate read-only
        validate_read_only(query)
        
        # Resolve database path
        db_path = self._resolve_database_path(database)
        
        async with aiosqlite.connect(db_path) as db:
            # Enable row factory for dict-like access
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            
            # Convert rows to list of dictionaries
            results = [dict(row) for row in rows]
            
            return {
                "query": query,
                "database": database or "default",
                "row_count": len(results),
                "results": results
            }
    
    async def explain_query(self, query: str, database: Optional[str] = None) -> Dict[str, Any]:
        """Get query execution plan (EXPLAIN QUERY PLAN).
        
        Args:
            query: SQL SELECT query
            database: Optional database/catalog name. If None, uses default database.
            
        Returns:
            Dictionary with execution plan including database information
        """
        # Validate read-only
        validate_read_only(query)
        
        # Resolve database path
        db_path = self._resolve_database_path(database)
        
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(f"EXPLAIN QUERY PLAN {query}")
            plan = await cursor.fetchall()
            
            return {
                "query": query,
                "database": database or "default",
                "execution_plan": [dict(row) for row in plan]
            }
