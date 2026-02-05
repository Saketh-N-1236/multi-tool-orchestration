"""Catalog manager with multi-catalog support (Unity Catalog-like)."""

import aiosqlite
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from config.settings import get_settings
from mcp_servers.catalog_server.database import CatalogDatabase

logger = logging.getLogger(__name__)


class CatalogManager:
    """Manages multiple catalogs and databases (Unity Catalog-like).
    
    Supports:
    - Multiple catalogs (databases)
    - Schema abstraction
    - Table metadata operations
    - Search functionality
    - Data lineage tracking
    """
    
    def __init__(self, catalog_configs: Optional[Dict[str, Dict[str, Any]]] = None):
        """Initialize catalog manager.
        
        Args:
            catalog_configs: Dictionary mapping catalog names to their configurations.
                Format: {
                    "catalog_name": {
                        "type": "sqlite",
                        "path": "path/to/database.db"
                    }
                }
        """
        self.settings = get_settings()
        
        # Default catalog configurations
        default_configs = {
            "main": {
                "type": "sqlite",
                "path": self.settings.database_path
            }
        }
        
        # Load catalog configs from settings if available
        if hasattr(self.settings, 'catalog_configs') and self.settings.catalog_configs:
            try:
                settings_configs = json.loads(self.settings.catalog_configs)
                if isinstance(settings_configs, dict):
                    default_configs.update(settings_configs)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse catalog_configs from settings: {e}")
        
        # Merge with provided configs (takes precedence)
        if catalog_configs:
            default_configs.update(catalog_configs)
        
        self.catalogs = default_configs
        
        # Lineage storage (simple JSON file for now)
        self.lineage_path = Path(self.settings.database_path).parent / "catalog_lineage.json"
        self._lineage_data = self._load_lineage()
        
        logger.info(f"Initialized CatalogManager with {len(self.catalogs)} catalog(s): {list(self.catalogs.keys())}")
    
    def _load_lineage(self) -> Dict[str, Any]:
        """Load lineage data from file.
        
        Returns:
            Dictionary with lineage information
        """
        if self.lineage_path.exists():
            try:
                with open(self.lineage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load lineage data: {e}")
                return {}
        return {}
    
    def _save_lineage(self):
        """Save lineage data to file."""
        try:
            self.lineage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.lineage_path, 'w', encoding='utf-8') as f:
                json.dump(self._lineage_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save lineage data: {e}")
    
    async def list_catalogs(self) -> List[str]:
        """List all available catalogs by scanning file system.
        
        This method scans the data directory for .db files and auto-registers
        any databases that aren't already in the catalog manager. This ensures
        that databases created via the CRUD API are visible to the MCP server.
        
        Returns:
            List of catalog names
        """
        # Get data directory (same location as CRUD API uses)
        data_dir = Path(self.settings.database_path).parent
        
        # Scan for .db files and auto-register them
        if data_dir.exists():
            for db_file in data_dir.glob("*.db"):
                db_name = db_file.stem
                # Auto-register if not already in catalogs
                if db_name not in self.catalogs:
                    self.catalogs[db_name] = {
                        "type": "sqlite",
                        "path": str(db_file)
                    }
                    logger.info(f"Auto-discovered catalog '{db_name}' from file system at {db_file}")
        
        return list(self.catalogs.keys())
    
    async def list_schemas(self, catalog_name: str) -> List[str]:
        """List schemas in a catalog.
        
        Args:
            catalog_name: Name of the catalog
            
        Returns:
            List of schema names
            
        Raises:
            ValueError: If catalog not found
        """
        if catalog_name not in self.catalogs:
            raise ValueError(f"Catalog '{catalog_name}' not found")
        
        catalog_config = self.catalogs[catalog_name]
        
        if catalog_config["type"] == "sqlite":
            # SQLite has one default schema "main"
            return ["main"]
        else:
            # For other database types, would query information_schema
            # For now, return empty list
            logger.warning(f"Schema listing not implemented for database type: {catalog_config['type']}")
            return []
    
    async def list_tables(
        self,
        catalog_name: str,
        schema_name: Optional[str] = None
    ) -> List[str]:
        """List tables in a catalog/schema.
        
        Args:
            catalog_name: Name of the catalog
            schema_name: Optional schema name (defaults to "main" for SQLite)
            
        Returns:
            List of table names
            
        Raises:
            ValueError: If catalog not found
        """
        if catalog_name not in self.catalogs:
            raise ValueError(f"Catalog '{catalog_name}' not found")
        
        catalog_config = self.catalogs[catalog_name]
        
        if catalog_config["type"] == "sqlite":
            # Use existing CatalogDatabase for SQLite
            db = CatalogDatabase(catalog_config["path"])
            return await db.list_tables()
        else:
            logger.warning(f"Table listing not implemented for database type: {catalog_config['type']}")
            return []
    
    async def describe_table(
        self,
        catalog_name: str,
        schema_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Get table metadata.
        
        Args:
            catalog_name: Name of the catalog
            schema_name: Name of the schema
            table_name: Name of the table
            
        Returns:
            Dictionary with table metadata including catalog and schema info
            
        Raises:
            ValueError: If catalog or table not found
        """
        if catalog_name not in self.catalogs:
            raise ValueError(f"Catalog '{catalog_name}' not found")
        
        catalog_config = self.catalogs[catalog_name]
        
        if catalog_config["type"] == "sqlite":
            # Use existing CatalogDatabase for SQLite
            db = CatalogDatabase(catalog_config["path"])
            metadata = await db.describe_table(table_name)
            
            # Add catalog and schema information
            metadata["catalog"] = catalog_name
            metadata["schema"] = schema_name
            
            # Get row count
            row_count = await db.get_table_row_count(table_name)
            metadata["row_count"] = row_count
            
            return metadata
        else:
            logger.warning(f"Table description not implemented for database type: {catalog_config['type']}")
            return {
                "catalog": catalog_name,
                "schema": schema_name,
                "table_name": table_name,
                "columns": []
            }
    
    async def search_tables(
        self,
        query: str,
        catalog_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search tables across catalogs.
        
        Args:
            query: Search query (table name pattern)
            catalog_name: Optional catalog to search in (searches all if None)
            
        Returns:
            List of matching tables with catalog and schema information
        """
        # CRITICAL: Auto-discover databases before searching to ensure all databases are found
        # This ensures databases created via CRUD API are visible to search
        if catalog_name is None:
            # Trigger auto-discovery by calling list_catalogs
            await self.list_catalogs()
        
        results = []
        query_lower = query.lower()
        
        catalogs_to_search = [catalog_name] if catalog_name else list(self.catalogs.keys())
        
        for cat_name in catalogs_to_search:
            if cat_name not in self.catalogs:
                continue
            
            try:
                tables = await self.list_tables(cat_name)
                schemas = await self.list_schemas(cat_name)
                
                for table in tables:
                    if query_lower in table.lower():
                        # Get schema (default to first schema for SQLite)
                        schema = schemas[0] if schemas else "main"
                        
                        results.append({
                            "catalog": cat_name,
                            "schema": schema,
                            "table": table
                        })
            except Exception as e:
                logger.warning(f"Error searching catalog '{cat_name}': {e}")
                continue
        
        return results
    
    async def get_lineage(
        self,
        catalog_name: str,
        schema_name: str,
        table_name: str
    ) -> Dict[str, Any]:
        """Get data lineage for a table.
        
        Args:
            catalog_name: Name of the catalog
            schema_name: Name of the schema
            table_name: Name of the table
            
        Returns:
            Dictionary with lineage information (upstream and downstream tables)
        """
        # Create lineage key
        lineage_key = f"{catalog_name}.{schema_name}.{table_name}"
        
        # Get lineage from storage
        lineage = self._lineage_data.get(lineage_key, {
            "upstream_tables": [],
            "downstream_tables": []
        })
        
        return {
            "catalog": catalog_name,
            "schema": schema_name,
            "table": table_name,
            "upstream_tables": lineage.get("upstream_tables", []),
            "downstream_tables": lineage.get("downstream_tables", [])
        }
    
    async def set_lineage(
        self,
        catalog_name: str,
        schema_name: str,
        table_name: str,
        upstream_tables: Optional[List[str]] = None,
        downstream_tables: Optional[List[str]] = None
    ):
        """Set data lineage for a table.
        
        Args:
            catalog_name: Name of the catalog
            schema_name: Name of the schema
            table_name: Name of the table
            upstream_tables: List of upstream table identifiers
            downstream_tables: List of downstream table identifiers
        """
        lineage_key = f"{catalog_name}.{schema_name}.{table_name}"
        
        if lineage_key not in self._lineage_data:
            self._lineage_data[lineage_key] = {
                "upstream_tables": [],
                "downstream_tables": []
            }
        
        if upstream_tables is not None:
            self._lineage_data[lineage_key]["upstream_tables"] = upstream_tables
        
        if downstream_tables is not None:
            self._lineage_data[lineage_key]["downstream_tables"] = downstream_tables
        
        self._save_lineage()
    
    def add_catalog(
        self,
        catalog_name: str,
        catalog_type: str,
        path: str
    ):
        """Add a new catalog.
        
        Args:
            catalog_name: Name of the catalog
            catalog_type: Type of database (e.g., "sqlite")
            path: Path to database file or connection string
        """
        self.catalogs[catalog_name] = {
            "type": catalog_type,
            "path": path
        }
        logger.info(f"Added catalog '{catalog_name}' of type '{catalog_type}'")
    
    def remove_catalog(self, catalog_name: str):
        """Remove a catalog.
        
        Args:
            catalog_name: Name of the catalog to remove
            
        Raises:
            ValueError: If catalog not found
        """
        if catalog_name not in self.catalogs:
            raise ValueError(f"Catalog '{catalog_name}' not found")
        
        if catalog_name == "main":
            raise ValueError("Cannot remove the 'main' catalog")
        
        del self.catalogs[catalog_name]
        logger.info(f"Removed catalog '{catalog_name}'")
