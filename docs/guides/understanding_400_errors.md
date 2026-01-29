# Understanding 400 Bad Request in MCP Servers

## Is 400 Bad Request an Error?

**Short Answer:** Not always! In MCP servers, 400 Bad Request is used for **validation errors**, which are expected and correct behavior.

## When You See 400 Bad Request

### ✅ Expected 400 Responses (Working Correctly)

1. **Read-Only Enforcement**
   - When trying to execute INSERT/UPDATE/DELETE queries on SQL Query server
   - Example: `INSERT INTO users ...` → 400 Bad Request ✅
   - This is **correct behavior** - the server is protecting the database

2. **Invalid Parameters**
   - Missing required parameters
   - Invalid parameter types
   - Parameter validation failures

3. **Business Logic Validation**
   - Query validation (e.g., SQL syntax errors)
   - Permission checks
   - Resource constraints

### ❌ Unexpected 400 Responses (Actual Errors)

1. **Malformed JSON-RPC Request**
   - Invalid JSON structure
   - Missing required JSON-RPC fields

2. **Authentication Failures**
   - These should return 401 Unauthorized, not 400

## How to Distinguish

### In Server Logs

**Validation Error (Expected):**
```
INFO: Validation error for method 'execute_query': Read-only mode: INSERT operations are not allowed
INFO: 127.0.0.1:56566 - "POST /execute HTTP/1.1" 400 Bad Request
```

**Internal Error (Unexpected):**
```
ERROR: Internal error executing method 'execute_query': Database connection failed
INFO: 127.0.0.1:56566 - "POST /execute HTTP/1.1" 500 Internal Server Error
```

### In JSON-RPC Response

**Validation Error (400):**
```json
{
  "jsonrpc": "2.0",
  "id": "123",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "Read-only mode: INSERT operations are not allowed"
  }
}
```

**Internal Error (500):**
```json
{
  "jsonrpc": "2.0",
  "id": "123",
  "error": {
    "code": -32603,
    "message": "Internal Error",
    "data": "Database connection failed"
  }
}
```

## JSON-RPC Error Codes

| Code | Meaning | HTTP Status | Example |
|------|---------|-------------|---------|
| -32600 | Invalid Request | 400 | Malformed JSON-RPC |
| -32601 | Method not found | 404 | Unknown tool name |
| -32602 | Invalid params | 400 | Read-only violation |
| -32603 | Internal error | 500 | Database error |

## In Your Test Output

When you see:
```
INFO: 127.0.0.1:56566 - "POST /execute HTTP/1.1" 400 Bad Request
```

And the test shows:
```
[OK] Read-only enforcement working
[OK] Error message: Invalid params: Read-only mode: INSERT operations are not allowed...
```

**This means:** ✅ Everything is working correctly! The 400 is the expected response.

## Summary

- **400 Bad Request** for validation errors = ✅ Correct behavior
- **400 Bad Request** for malformed requests = ⚠️ Client issue
- **500 Internal Server Error** = ❌ Server problem

The read-only enforcement test intentionally triggers a 400 response to verify the protection is working. This is **not a bug** - it's a **feature**! 🎯
