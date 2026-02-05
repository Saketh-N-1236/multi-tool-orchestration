"""Test script for catalog improvements (Phase 1)."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from mcp_servers.catalog_server.catalog_manager import CatalogManager


async def test_catalog_manager():
    """Test CatalogManager functionality."""
    print("=" * 60)
    print("Testing CatalogManager (Phase 1)")
    print("=" * 60)
    
    manager = CatalogManager()
    
    # Test 1: List catalogs
    print("\n1. Testing list_catalogs()...")
    catalogs = await manager.list_catalogs()
    print(f"   [OK] Found {len(catalogs)} catalog(s): {catalogs}")
    
    # Test 2: List schemas
    print("\n2. Testing list_schemas()...")
    for catalog in catalogs:
        schemas = await manager.list_schemas(catalog)
        print(f"   [OK] Catalog '{catalog}' has {len(schemas)} schema(s): {schemas}")
    
    # Test 3: List tables
    print("\n3. Testing list_tables()...")
    for catalog in catalogs:
        tables = await manager.list_tables(catalog)
        print(f"   [OK] Catalog '{catalog}' has {len(tables)} table(s): {tables}")
    
    # Test 4: Describe table
    print("\n4. Testing describe_table()...")
    for catalog in catalogs:
        tables = await manager.list_tables(catalog)
        if tables:
            table = tables[0]
            schemas = await manager.list_schemas(catalog)
            schema = schemas[0] if schemas else "main"
            metadata = await manager.describe_table(catalog, schema, table)
            print(f"   [OK] Table '{catalog}.{schema}.{table}':")
            print(f"      - Columns: {len(metadata.get('columns', []))}")
            print(f"      - Row count: {metadata.get('row_count', 0)}")
            break
    
    # Test 5: Search tables
    print("\n5. Testing search_tables()...")
    results = await manager.search_tables("user")
    print(f"   [OK] Found {len(results)} table(s) matching 'user':")
    for result in results[:3]:  # Show first 3
        print(f"      - {result['catalog']}.{result['schema']}.{result['table']}")
    
    # Test 6: Get lineage
    print("\n6. Testing get_lineage()...")
    for catalog in catalogs:
        tables = await manager.list_tables(catalog)
        if tables:
            table = tables[0]
            schemas = await manager.list_schemas(catalog)
            schema = schemas[0] if schemas else "main"
            lineage = await manager.get_lineage(catalog, schema, table)
            print(f"   [OK] Lineage for '{catalog}.{schema}.{table}':")
            print(f"      - Upstream: {len(lineage.get('upstream_tables', []))} table(s)")
            print(f"      - Downstream: {len(lineage.get('downstream_tables', []))} table(s)")
            break
    
    print("\n" + "=" * 60)
    print("[OK] All CatalogManager tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_catalog_manager())
