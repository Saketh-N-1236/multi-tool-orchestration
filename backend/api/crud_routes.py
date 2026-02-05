"""CRUD API routes for database, table, and row operations."""

import aiosqlite
import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from config.settings import get_settings
from mcp_servers.catalog_server.catalog_manager import CatalogManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["CRUD"])
settings = get_settings()


# Request/Response Models
class CreateDatabaseRequest(BaseModel):
    """Request model for creating a database."""
    name: str = Field(..., description="Database name")
    type: str = Field(default="sqlite", description="Database type (sqlite, postgresql, mysql)")


class CreateTableRequest(BaseModel):
    """Request model for creating a table."""
    table_name: str = Field(..., description="Table name")
    columns: List[Dict[str, Any]] = Field(..., description="Column definitions")
    # Example: [{"name": "id", "type": "INTEGER", "primary_key": True}, ...]


class InsertRowRequest(BaseModel):
    """Request model for inserting a row."""
    data: Dict[str, Any] = Field(..., description="Row data as key-value pairs")


class UpdateRowRequest(BaseModel):
    """Request model for updating a row."""
    data: Dict[str, Any] = Field(..., description="Updated row data")


class DatabaseManager:
    """Manages database operations for CRUD endpoints."""
    
    def __init__(self):
        self.settings = get_settings()
        self.catalog_manager = CatalogManager()
        self.data_dir = Path(self.settings.database_path).parent
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_db_path(self, database_name: str) -> Path:
        """Get database file path."""
        return self.data_dir / f"{database_name}.db"
    
    async def create_database(self, name: str, db_type: str = "sqlite") -> Dict[str, Any]:
        """Create a new database."""
        if db_type != "sqlite":
            raise HTTPException(status_code=400, detail=f"Database type '{db_type}' not yet supported")
        
        # Validate database name
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
            raise HTTPException(status_code=400, detail="Invalid database name. Must start with letter and contain only alphanumeric and underscore")
        
        db_path = self._get_db_path(name)
        
        if db_path.exists():
            raise HTTPException(status_code=409, detail=f"Database '{name}' already exists")
        
        # Create empty SQLite database
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.commit()
        
        # Add to catalog manager
        self.catalog_manager.add_catalog(name, "sqlite", str(db_path))
        
        logger.info(f"Created database '{name}' at {db_path}")
        
        return {
            "name": name,
            "type": db_type,
            "path": str(db_path),
            "created": True
        }
    
    async def list_databases(self) -> List[Dict[str, Any]]:
        """List all databases by scanning the data directory."""
        databases = []
        database_files = {}
        
        # Scan data directory for all .db files
        if self.data_dir.exists():
            for db_file in self.data_dir.glob("*.db"):
                # Extract database name from filename (remove .db extension)
                db_name = db_file.stem
                database_files[db_name] = db_file
        
        # Get catalogs from catalog manager (for in-memory ones)
        try:
            catalogs = await self.catalog_manager.list_catalogs()
            for catalog in catalogs:
                if catalog not in database_files:
                    # Catalog exists in manager but file might not exist yet
                    # Try to get path from catalog manager
                    if catalog in self.catalog_manager.catalogs:
                        catalog_path = Path(self.catalog_manager.catalogs[catalog]["path"])
                        if catalog_path.exists():
                            database_files[catalog] = catalog_path
        except Exception as e:
            logger.warning(f"Error getting catalogs from catalog manager: {e}")
        
        # Process all found databases
        for db_name, db_path in database_files.items():
            try:
                # Ensure catalog is registered in catalog manager
                if db_name not in self.catalog_manager.catalogs:
                    self.catalog_manager.add_catalog(db_name, "sqlite", str(db_path))
                    logger.info(f"Auto-registered database '{db_name}' from file system")
                
                # Get table and schema info
                tables = await self.catalog_manager.list_tables(db_name)
                schemas = await self.catalog_manager.list_schemas(db_name)
                
                databases.append({
                    "name": db_name,
                    "type": "sqlite",
                    "table_count": len(tables),
                    "schema_count": len(schemas)
                })
            except Exception as e:
                logger.warning(f"Error getting info for database '{db_name}': {e}")
                # Still include the database even if we can't get its info
                databases.append({
                    "name": db_name,
                    "type": "sqlite",
                    "table_count": 0,
                    "schema_count": 0
                })
        
        # Sort by name for consistent ordering
        databases.sort(key=lambda x: x["name"])
        
        return databases
    
    async def delete_database(self, name: str) -> Dict[str, Any]:
        """Delete a database."""
        if name == "main":
            raise HTTPException(status_code=400, detail="Cannot delete the 'main' database")
        
        db_path = self._get_db_path(name)
        
        if not db_path.exists():
            raise HTTPException(status_code=404, detail=f"Database '{name}' not found")
        
        # Remove from catalog manager
        try:
            self.catalog_manager.remove_catalog(name)
        except ValueError:
            pass  # Already removed or doesn't exist
        
        # Delete database file
        db_path.unlink()
        
        logger.info(f"Deleted database '{name}'")
        
        return {
            "name": name,
            "deleted": True
        }
    
    async def create_table(
        self,
        database_name: str,
        table_name: str,
        columns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a table in a database."""
        # Get database path
        catalog_config = self.catalog_manager.catalogs.get(database_name)
        if not catalog_config:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        if catalog_config["type"] != "sqlite":
            raise HTTPException(status_code=400, detail=f"Table creation not yet supported for database type '{catalog_config['type']}'")
        
        db_path = catalog_config["path"]
        
        # Validate table name
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', table_name):
            raise HTTPException(status_code=400, detail="Invalid table name. Must start with letter and contain only alphanumeric and underscore")
        
        # Check if table exists
        existing_tables = await self.catalog_manager.list_tables(database_name)
        if table_name in existing_tables:
            raise HTTPException(status_code=409, detail=f"Table '{table_name}' already exists")
        
        # Build CREATE TABLE SQL
        column_defs = []
        for col in columns:
            col_name = col.get("name")
            col_type = col.get("type", "TEXT")
            col_def = f"{col_name} {col_type}"
            
            if col.get("primary_key"):
                col_def += " PRIMARY KEY"
            if col.get("not_null"):
                col_def += " NOT NULL"
            if col.get("default") is not None:
                default_val = col.get("default")
                if isinstance(default_val, str):
                    col_def += f" DEFAULT '{default_val}'"
                else:
                    col_def += f" DEFAULT {default_val}"
            
            column_defs.append(col_def)
        
        create_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"
        
        # Execute CREATE TABLE
        async with aiosqlite.connect(db_path) as db:
            await db.execute(create_sql)
            await db.commit()
        
        logger.info(f"Created table '{table_name}' in database '{database_name}'")
        
        return {
            "database": database_name,
            "table": table_name,
            "created": True
        }
    
    async def list_tables(self, database_name: str) -> List[Dict[str, Any]]:
        """List tables in a database."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        tables = await self.catalog_manager.list_tables(database_name)
        
        table_info = []
        for table in tables:
            try:
                schemas = await self.catalog_manager.list_schemas(database_name)
                schema = schemas[0] if schemas else "main"
                metadata = await self.catalog_manager.describe_table(database_name, schema, table)
                table_info.append({
                    "name": table,
                    "column_count": len(metadata.get("columns", [])),
                    "row_count": metadata.get("row_count", 0)
                })
            except Exception as e:
                logger.warning(f"Error getting info for table '{table}': {e}")
                table_info.append({
                    "name": table,
                    "column_count": 0,
                    "row_count": 0
                })
        
        return table_info
    
    async def delete_table(self, database_name: str, table_name: str) -> Dict[str, Any]:
        """Delete a table."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        catalog_config = self.catalog_manager.catalogs[database_name]
        db_path = catalog_config["path"]
        
        # Check if table exists
        tables = await self.catalog_manager.list_tables(database_name)
        if table_name not in tables:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        
        # Execute DROP TABLE
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"DROP TABLE {table_name}")
            await db.commit()
        
        logger.info(f"Deleted table '{table_name}' from database '{database_name}'")
        
        return {
            "database": database_name,
            "table": table_name,
            "deleted": True
        }
    
    async def insert_row(
        self,
        database_name: str,
        table_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Insert a row into a table."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        catalog_config = self.catalog_manager.catalogs[database_name]
        db_path = catalog_config["path"]
        
        # Get table schema
        schemas = await self.catalog_manager.list_schemas(database_name)
        schema = schemas[0] if schemas else "main"
        metadata = await self.catalog_manager.describe_table(database_name, schema, table_name)
        
        # Build INSERT SQL
        columns = list(data.keys())
        placeholders = ", ".join(["?" for _ in columns])
        values = [data[col] for col in columns]
        
        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
        
        # Execute INSERT
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(insert_sql, values)
            await db.commit()
            row_id = cursor.lastrowid
        
        logger.info(f"Inserted row into '{database_name}.{table_name}' with id {row_id}")
        
        return {
            "database": database_name,
            "table": table_name,
            "id": row_id,
            "data": data
        }
    
    async def list_rows(
        self,
        database_name: str,
        table_name: str,
        limit: int = 100,
        offset: int = 0,
        where: Optional[str] = None
    ) -> Dict[str, Any]:
        """List rows from a table."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        catalog_config = self.catalog_manager.catalogs[database_name]
        db_path = catalog_config["path"]
        
        # Build SELECT SQL
        select_sql = f"SELECT * FROM {table_name}"
        params = []
        
        if where:
            # Basic WHERE clause validation (prevent SQL injection)
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\s*[=<>]+\s*[\'"]?[a-zA-Z0-9_]+[\'"]?$', where.strip()):
                raise HTTPException(status_code=400, detail="Invalid WHERE clause format")
            select_sql += f" WHERE {where}"
        
        select_sql += f" LIMIT {limit} OFFSET {offset}"
        
        # Execute SELECT
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(select_sql, params)
            rows = await cursor.fetchall()
            
            # Get total count
            count_sql = f"SELECT COUNT(*) FROM {table_name}"
            if where:
                count_sql += f" WHERE {where}"
            count_cursor = await db.execute(count_sql, params)
            total_count = (await count_cursor.fetchone())[0]
        
        results = [dict(row) for row in rows]
        
        return {
            "database": database_name,
            "table": table_name,
            "rows": results,
            "count": len(results),
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    
    async def update_row(
        self,
        database_name: str,
        table_name: str,
        row_id: int,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a row in a table."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        catalog_config = self.catalog_manager.catalogs[database_name]
        db_path = catalog_config["path"]
        
        # Build UPDATE SQL
        set_clauses = [f"{col} = ?" for col in data.keys()]
        values = list(data.values())
        values.append(row_id)
        
        update_sql = f"UPDATE {table_name} SET {', '.join(set_clauses)} WHERE rowid = ?"
        
        # Execute UPDATE
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(update_sql, values)
            await db.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Row with id {row_id} not found")
        
        logger.info(f"Updated row {row_id} in '{database_name}.{table_name}'")
        
        return {
            "database": database_name,
            "table": table_name,
            "id": row_id,
            "data": data,
            "updated": True
        }
    
    async def delete_row(
        self,
        database_name: str,
        table_name: str,
        row_id: int
    ) -> Dict[str, Any]:
        """Delete a row from a table."""
        if database_name not in self.catalog_manager.catalogs:
            raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
        
        catalog_config = self.catalog_manager.catalogs[database_name]
        db_path = catalog_config["path"]
        
        # Execute DELETE
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(f"DELETE FROM {table_name} WHERE rowid = ?", (row_id,))
            await db.commit()
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Row with id {row_id} not found")
        
        logger.info(f"Deleted row {row_id} from '{database_name}.{table_name}'")
        
        return {
            "database": database_name,
            "table": table_name,
            "id": row_id,
            "deleted": True
        }


# Initialize database manager
db_manager = DatabaseManager()


# Database CRUD Endpoints
@router.post("/databases", response_model=Dict[str, Any])
async def create_database(request: CreateDatabaseRequest):
    """Create a new database."""
    return await db_manager.create_database(request.name, request.type)


@router.get("/databases", response_model=List[Dict[str, Any]])
async def list_databases():
    """List all databases."""
    return await db_manager.list_databases()


@router.get("/databases/{database_name}", response_model=Dict[str, Any])
async def get_database(database_name: str):
    """Get database information."""
    databases = await db_manager.list_databases()
    db = next((d for d in databases if d["name"] == database_name), None)
    if not db:
        raise HTTPException(status_code=404, detail=f"Database '{database_name}' not found")
    return db


@router.delete("/databases/{database_name}", response_model=Dict[str, Any])
async def delete_database(database_name: str):
    """Delete a database."""
    return await db_manager.delete_database(database_name)


# Table CRUD Endpoints
@router.post("/databases/{database_name}/tables", response_model=Dict[str, Any])
async def create_table(database_name: str, request: CreateTableRequest):
    """Create a table in a database."""
    return await db_manager.create_table(database_name, request.table_name, request.columns)


@router.get("/databases/{database_name}/tables", response_model=List[Dict[str, Any]])
async def list_tables(database_name: str):
    """List tables in a database."""
    return await db_manager.list_tables(database_name)


@router.get("/databases/{database_name}/tables/{table_name}", response_model=Dict[str, Any])
async def get_table(database_name: str, table_name: str):
    """Get table information."""
    tables = await db_manager.list_tables(database_name)
    table = next((t for t in tables if t["name"] == table_name), None)
    if not table:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    
    # Get full schema
    schemas = await db_manager.catalog_manager.list_schemas(database_name)
    schema = schemas[0] if schemas else "main"
    metadata = await db_manager.catalog_manager.describe_table(database_name, schema, table_name)
    
    return {
        "name": table_name,
        "database": database_name,
        "schema": metadata
    }


@router.delete("/databases/{database_name}/tables/{table_name}", response_model=Dict[str, Any])
async def delete_table(database_name: str, table_name: str):
    """Delete a table."""
    return await db_manager.delete_table(database_name, table_name)


# Row CRUD Endpoints
@router.post("/databases/{database_name}/tables/{table_name}/rows", response_model=Dict[str, Any])
async def insert_row(database_name: str, table_name: str, request: InsertRowRequest):
    """Insert a row into a table."""
    return await db_manager.insert_row(database_name, table_name, request.data)


@router.get("/databases/{database_name}/tables/{table_name}/rows", response_model=Dict[str, Any])
async def list_rows(
    database_name: str,
    table_name: str,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    where: Optional[str] = Query(default=None, description="WHERE clause (e.g., 'id=1')")
):
    """List rows from a table."""
    return await db_manager.list_rows(database_name, table_name, limit, offset, where)


@router.get("/databases/{database_name}/tables/{table_name}/rows/{row_id}", response_model=Dict[str, Any])
async def get_row(database_name: str, table_name: str, row_id: int):
    """Get a specific row by ID."""
    result = await db_manager.list_rows(database_name, table_name, limit=1, offset=0, where=f"rowid={row_id}")
    if result["count"] == 0:
        raise HTTPException(status_code=404, detail=f"Row with id {row_id} not found")
    return result["rows"][0]


@router.put("/databases/{database_name}/tables/{table_name}/rows/{row_id}", response_model=Dict[str, Any])
async def update_row(database_name: str, table_name: str, row_id: int, request: UpdateRowRequest):
    """Update a row in a table."""
    return await db_manager.update_row(database_name, table_name, row_id, request.data)


@router.delete("/databases/{database_name}/tables/{table_name}/rows/{row_id}", response_model=Dict[str, Any])
async def delete_row(database_name: str, table_name: str, row_id: int):
    """Delete a row from a table."""
    return await db_manager.delete_row(database_name, table_name, row_id)
