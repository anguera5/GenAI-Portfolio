# Logging Examples

This document shows real-world examples of what logs look like in the GenAI Portfolio application.

## Backend Logs

### Example 1: Successful Code Generation

```
2025-11-13T16:30:45Z INFO root [REQUEST] id=1699893045123-140234 method=POST path=/api/generate client=127.0.0.1
2025-11-13T16:30:45Z INFO app.api.routes [USER_ACTION][generate] lang=python prompt.len=125
2025-11-13T16:30:47Z INFO app.api.routes [SUCCESS][generate] lang=python response.len=456
2025-11-13T16:30:47Z INFO root [RESPONSE] id=1699893045123-140234 status=200 duration=2.345s
```

**What this shows:**
- User made a POST request to generate code
- Request ID: 1699893045123-140234
- Client IP: 127.0.0.1
- Language: Python
- Prompt length: 125 characters
- Response length: 456 characters
- Total duration: 2.345 seconds

### Example 2: Error in Test Generation

```
2025-11-13T16:35:20Z INFO root [REQUEST] id=1699893320456-140235 method=POST path=/api/tests client=192.168.1.100
2025-11-13T16:35:20Z INFO app.api.routes [USER_ACTION][tests] code.len=789
2025-11-13T16:35:22Z ERROR app.api.routes [ERROR][tests] error=Invalid API key or upstream not reachable.
Traceback (most recent call last):
  File "app/api/routes.py", line 51, in generate_tests
    text = llm.generate_tests(payload.code)
  File "app/services/llm_model.py", line 125, in generate_tests
    raise HTTPException(status_code=401, detail="Invalid API key")
HTTPException: Invalid API key or upstream not reachable.
2025-11-13T16:35:22Z INFO root [RESPONSE] id=1699893320456-140235 status=401 duration=1.234s
```

**What this shows:**
- User attempted to generate tests
- Code input length: 789 characters
- Error occurred: Invalid API key
- Full stack trace captured
- HTTP 401 status returned
- Total duration: 1.234 seconds

### Example 3: ChEMBL Query Execution

```
2025-11-13T17:00:00Z INFO root [REQUEST] id=1699894800789-140236 method=POST path=/api/chembl-agent/run client=10.0.0.50
2025-11-13T17:00:00Z INFO app.api.routes [USER_ACTION][chembl/run] prompt.len=87
2025-11-13T17:00:15Z INFO app.api.routes [SUCCESS][chembl/run] response summary: cols=5 rows=100 retries=1 repaired=True
2025-11-13T17:00:15Z INFO root [RESPONSE] id=1699894800789-140236 status=200 duration=15.234s
```

**What this shows:**
- ChEMBL query executed
- Prompt length: 87 characters
- Results: 5 columns, 100 rows
- Query was retried and repaired once
- Total duration: 15.234 seconds

### Example 4: Code Review Webhook

```
2025-11-13T18:00:00Z INFO root [REQUEST] id=1699898400123-140237 method=POST path=/api/code-review/webhook client=140.82.115.0
2025-11-13T18:00:00Z INFO app.api.routes [USER_ACTION][code-review/webhook] Received webhook request
2025-11-13T18:00:00Z INFO app.api.routes [USER_ACTION][code-review/webhook] PR details: title=Add new feature action=opened base=main head=feature-branch
2025-11-13T18:00:05Z INFO app.api.routes [SUCCESS][code-review/webhook] Generated review for: Add new feature
2025-11-13T18:00:06Z INFO app.api.routes [SUCCESS][code-review/webhook] Post attempted on owner/repo#123
2025-11-13T18:00:06Z INFO app.api.routes [SUCCESS][code-review/webhook] Response: ok: pr=Add new feature base=main head=feature-branch diff bot action=opened queued
2025-11-13T18:00:06Z INFO root [RESPONSE] id=1699898400123-140237 status=200 duration=6.123s
```

**What this shows:**
- GitHub webhook received
- PR opened event
- Review generated and posted
- PR #123 in owner/repo
- Background task queued
- Total duration: 6.123 seconds

## Frontend Logs

### Example 1: Application Startup

```javascript
[2025-11-13T16:30:00.123Z] [INFO] [APP] Application starting { environment: 'development', timestamp: '2025-11-13T16:30:00.123Z' }
[2025-11-13T16:30:00.234Z] [INFO] [APP] Application mounted successfully
[2025-11-13T16:30:00.345Z] [INFO] [NAVIGATION] (initial) → /
```

### Example 2: User Generating Code

```javascript
[2025-11-13T16:30:45.123Z] [INFO] [USER_ACTION] Generate Code Button Clicked { language: 'python', promptLength: 125 }
[2025-11-13T16:30:45.234Z] [INFO] [API_REQUEST] POST /api/generate { prompt: '...', language: 'python', api_key: '[REDACTED]' }
[2025-11-13T16:30:47.345Z] [INFO] [API_RESPONSE] POST /api/generate - 200 (2111ms) { status: 200, statusText: 'OK' }
[2025-11-13T16:30:47.456Z] [INFO] [CODE_GENERATOR] Code generated successfully { language: 'python', codeLength: 456 }
```

**What this shows:**
- User clicked "Generate Code" button
- Language: Python
- Prompt: 125 characters
- API key automatically redacted
- Request took 2111ms
- Generated 456 characters of code

### Example 3: User Navigation

```javascript
[2025-11-13T16:35:00.123Z] [INFO] [NAVIGATION] /code-generator → /chembl-agent
[2025-11-13T16:35:05.234Z] [INFO] [USER_ACTION] ChEMBL Query Submit { promptLength: 87 }
[2025-11-13T16:35:05.345Z] [INFO] [API_REQUEST] POST /api/chembl-agent/run { prompt: '...', api_key: '[REDACTED]' }
[2025-11-13T16:35:20.456Z] [INFO] [API_RESPONSE] POST /api/chembl-agent/run - 200 (15111ms) { status: 200, statusText: 'OK' }
```

**What this shows:**
- User navigated from code generator to ChEMBL agent
- Submitted a query with 87 characters
- API key redacted
- Request took 15.111 seconds

### Example 4: API Error

```javascript
[2025-11-13T16:40:00.123Z] [INFO] [USER_ACTION] Generate Tests Button Clicked { codeLength: 789 }
[2025-11-13T16:40:00.234Z] [INFO] [API_REQUEST] POST /api/tests { code: '...' }
[2025-11-13T16:40:01.345Z] [ERROR] [API_ERROR] POST /api/tests - Failed (1111ms) {
  status: 401,
  message: 'Invalid API key or upstream not reachable.',
  responseData: { detail: 'Invalid API key or upstream not reachable.' },
  code: 'ERR_BAD_REQUEST'
}
[2025-11-13T16:40:01.456Z] [ERROR] [CODE_GENERATOR] Test generation failed Error: Request failed with status code 401
    at createError (http.ts:25)
    at settle (http.ts:42)
Stack trace: ...
```

**What this shows:**
- User tried to generate tests
- Code length: 789 characters
- API request failed after 1.111 seconds
- Error: Invalid API key (401)
- Full error details and stack trace logged

### Example 5: Global Error Handler

```javascript
[2025-11-13T16:45:00.123Z] [ERROR] [GLOBAL] Uncaught error {
  error: 'TypeError: Cannot read property "value" of undefined',
  data: {
    message: "Cannot read property 'value' of undefined",
    filename: 'CodeGeneratorApp.vue',
    lineno: 245
  }
}
Stack trace: TypeError: Cannot read property 'value' of undefined
    at CodeGeneratorApp.vue:245:12
    at Array.forEach (<anonymous>)
    ...
```

**What this shows:**
- Uncaught error in CodeGeneratorApp.vue
- Line 245
- TypeError with property access
- Full stack trace captured

### Example 6: User Copying Code

```javascript
[2025-11-13T16:50:00.123Z] [INFO] [USER_ACTION] Copy Code/Tests { tab: 'code', length: 456 }
```

**What this shows:**
- User clicked copy button
- Copied from "code" tab
- 456 characters copied

### Example 7: User Downloading Code

```javascript
[2025-11-13T16:55:00.123Z] [INFO] [USER_ACTION] Download Code/Tests { tab: 'tests', length: 789 }
```

**What this shows:**
- User clicked download button
- Downloaded from "tests" tab
- 789 characters downloaded

## Log Analysis Examples

### Finding All Errors

**Backend:**
```bash
grep ERROR /var/log/genai-portfolio/app.log
```

**Frontend:**
Open browser console and filter by "ERROR"

### Tracking a Specific User Journey (Backend)

```bash
# Find a specific request ID
grep "id=1699893045123-140234" /var/log/genai-portfolio/app.log

# Output:
# 2025-11-13T16:30:45Z INFO root [REQUEST] id=1699893045123-140234 method=POST path=/api/generate client=127.0.0.1
# 2025-11-13T16:30:47Z INFO root [RESPONSE] id=1699893045123-140234 status=200 duration=2.345s
```

### Finding Slow Requests (Backend)

```bash
# Find requests that took more than 10 seconds
grep "duration=1[0-9]\." /var/log/genai-portfolio/app.log
grep "duration=2[0-9]\." /var/log/genai-portfolio/app.log
```

### Finding All User Actions (Backend)

```bash
grep "\[USER_ACTION\]" /var/log/genai-portfolio/app.log
```

### Finding Failed API Calls (Backend)

```bash
grep "\[ERROR\]" /var/log/genai-portfolio/app.log
```

### Export Frontend Logs for Analysis

```javascript
// In browser console
logger.exportLogs()
// Copy the JSON output for analysis
```

## Performance Insights from Logs

From the logs above, we can see:

1. **Average response times:**
   - Code generation: ~2-3 seconds
   - Test generation: ~1-2 seconds  
   - ChEMBL queries: ~15 seconds (complex database operations)
   - Code review: ~6 seconds

2. **Error patterns:**
   - Most common: Invalid API key (401)
   - Solution: Ensure users configure API key properly

3. **User journey:**
   - Users typically: Generate code → Add docs → Add tests
   - Common navigation: Home → Code Generator → other modules

4. **Data protection:**
   - API keys always redacted: `api_key: '[REDACTED]'`
   - Only metadata logged, not full content

## Summary

The logging system provides comprehensive visibility into:
- ✅ Every user action (button clicks, form submissions)
- ✅ Every API request and response
- ✅ Navigation between pages
- ✅ All errors with full context
- ✅ Performance metrics (request duration)
- ✅ Security events

All while protecting sensitive data and maintaining readable, searchable logs.
