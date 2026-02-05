"""Comprehensive endpoint testing."""
import asyncio
import httpx
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BASE_URL = "http://localhost:8000"

async def test_endpoint(name: str, method: str, url: str, **kwargs):
    """Test a single endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, **kwargs)
            elif method.upper() == "POST":
                response = await client.post(url, **kwargs)
            elif method.upper() == "DELETE":
                response = await client.delete(url, **kwargs)
            
            print(f"Status: {response.status_code}")
            
            if response.status_code < 400:
                try:
                    data = response.json()
                    print(f"✅ Success")
                    if isinstance(data, dict):
                        # Print key fields
                        for key in ["status", "count", "response", "tools", "collections"]:
                            if key in data:
                                value = data[key]
                                if isinstance(value, list) and len(value) > 3:
                                    print(f"   {key}: {value[:3]}... ({len(value)} items)")
                                else:
                                    print(f"   {key}: {value}")
                    return True
                except Exception as json_error:
                    print(f"✅ Success (non-JSON response)")
                    print(f"   Response: {response.text[:200]}")
                    return True
            else:
                try:
                    error_data = response.json()
                    error_detail = error_data.get("detail", error_data.get("error", response.text[:200]))
                    print(f"❌ Failed: {error_detail}")
                except:
                    print(f"❌ Failed: {response.text[:200]}")
                return False
    except httpx.ConnectError as e:
        print(f"❌ Connection Error: Cannot connect to {url}")
        print(f"   Make sure the API server is running on {BASE_URL}")
        return False
    except httpx.TimeoutException as e:
        print(f"❌ Timeout Error: Request to {url} timed out after 60 seconds")
        return False
    except Exception as e:
        import traceback
        error_msg = str(e) or repr(e)
        error_type = type(e).__name__
        print(f"❌ Error: {error_type}: {error_msg}")
        # Print full traceback for debugging
        traceback.print_exc()
        return False

async def main():
    """Test all endpoints."""
    print("="*60)
    print("ENDPOINT TESTING")
    print("="*60)
    print("\n⚠️  Make sure MCP servers are running before testing!")
    print("   Start servers with: python scripts/start_servers.py")
    print("="*60)
    
    results = {}
    
    # 1. Health check
    results["health"] = await test_endpoint(
        "GET /health",
        "GET",
        f"{BASE_URL}/health"
    )
    
    # 2. API Health
    results["api_health"] = await test_endpoint(
        "GET /api/v1/health",
        "GET",
        f"{BASE_URL}/api/v1/health"
    )
    
    # 3. Tools endpoint
    results["tools"] = await test_endpoint(
        "GET /api/v1/tools",
        "GET",
        f"{BASE_URL}/api/v1/tools"
    )
    
    # 4. Status endpoint
    results["status"] = await test_endpoint(
        "GET /api/v1/status",
        "GET",
        f"{BASE_URL}/api/v1/status"
    )
    
    # 5. List collections
    results["list_collections"] = await test_endpoint(
        "GET /api/v1/documents/collections",
        "GET",
        f"{BASE_URL}/api/v1/documents/collections"
    )
    
    # 6. Chat endpoint
    results["chat"] = await test_endpoint(
        "POST /api/v1/chat",
        "POST",
        f"{BASE_URL}/api/v1/chat",
        json={
            "message": "List all tables in the database",
            "max_iterations": 5
        }
    )
    
    # 7. Logs endpoint
    results["logs"] = await test_endpoint(
        "GET /api/v1/logs",
        "GET",
        f"{BASE_URL}/api/v1/logs?limit=10"
    )
    
    # 8. Analytics endpoints
    results["analytics_overview"] = await test_endpoint(
        "GET /api/v1/analytics/overview",
        "GET",
        f"{BASE_URL}/api/v1/analytics/overview"
    )
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for endpoint, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {endpoint}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

if __name__ == "__main__":
    asyncio.run(main())