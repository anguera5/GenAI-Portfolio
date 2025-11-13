# Logging Implementation Guide

This document describes the comprehensive logging solution implemented for both backend and frontend of the GenAI Portfolio application.

## Overview

The logging system captures:
- **Backend**: All HTTP requests/responses, user actions, errors, and application flow
- **Frontend**: User interactions, API calls, navigation, and errors

## Backend Logging

### Architecture

The backend uses Python's built-in `logging` module with the following features:

1. **File-based logging** with daily rotation (14 days retention)
2. **Console logging** for container/development environments
3. **Request/Response middleware** for comprehensive HTTP logging
4. **Structured log messages** with categorization

### Log Location

- **File**: `/var/log/genai-portfolio/app.log`
- **Rotation**: Daily at UTC midnight
- **Format**: `YYYY-MM-DDTHH:MM:SSZ LEVEL MODULE MESSAGE`

### Log Categories

Backend logs use tagged categories for easy filtering:

- `[REQUEST]` - Incoming HTTP requests
- `[RESPONSE]` - Outgoing HTTP responses
- `[USER_ACTION]` - User-initiated actions (generate, tests, docs, etc.)
- `[SUCCESS]` - Successful operations
- `[ERROR]` - Errors and exceptions
- `[SECURITY]` - Security-related events

### Example Backend Logs

```
2025-11-13T16:30:45Z INFO root [REQUEST] id=1699893045123-140234 method=POST path=/api/generate client=127.0.0.1
2025-11-13T16:30:45Z INFO app.api.routes [USER_ACTION][generate] lang=python prompt.len=125
2025-11-13T16:30:47Z INFO app.api.routes [SUCCESS][generate] lang=python response.len=456
2025-11-13T16:30:47Z INFO root [RESPONSE] id=1699893045123-140234 status=200 duration=2.345s
```

### Middleware Features

The `RequestLoggingMiddleware` automatically logs:
- Request ID (timestamp + object ID)
- HTTP method and path
- Client IP address
- Query parameters (if present)
- Response status code
- Request duration
- Errors with full stack traces

## Frontend Logging

### Architecture

The frontend uses a custom TypeScript logger utility (`src/lib/logger.ts`) with:

1. **Console logging** with colored output by severity
2. **In-memory log buffer** (last 1000 logs)
3. **HTTP interceptors** for automatic API logging
4. **Router guards** for navigation logging
5. **Global error handlers** for unhandled exceptions

### Log Levels

- `DEBUG` - Development-only verbose logging
- `INFO` - General informational messages
- `WARN` - Warnings and potential issues
- `ERROR` - Errors and exceptions

### Log Categories

Frontend logs use categorized logging:

- `API_REQUEST` - Outgoing API calls
- `API_RESPONSE` - API responses
- `API_ERROR` - API failures
- `USER_ACTION` - User interactions (clicks, form submissions)
- `NAVIGATION` - Route changes
- `ROUTER` - Router errors
- `GLOBAL` - Uncaught errors and promise rejections
- `APP` - Application lifecycle events

### Example Frontend Logs

```javascript
[2025-11-13T16:30:45.123Z] [INFO] [APP] Application starting
[2025-11-13T16:30:45.234Z] [INFO] [NAVIGATION] / → /code-generator
[2025-11-13T16:30:46.345Z] [INFO] [USER_ACTION] Generate Code Button Clicked { language: 'python', promptLength: 125 }
[2025-11-13T16:30:46.456Z] [INFO] [API_REQUEST] POST /api/generate { prompt: '...', language: 'python' }
[2025-11-13T16:30:48.567Z] [INFO] [API_RESPONSE] POST /api/generate - 200 (2111ms)
[2025-11-13T16:30:48.678Z] [INFO] [CODE_GENERATOR] Code generated successfully { language: 'python', codeLength: 456 }
```

### Logger API

The logger provides the following methods:

```typescript
// Basic logging
logger.info(category: string, message: string, data?: any)
logger.warn(category: string, message: string, data?: any)
logger.error(category: string, message: string, error?: Error, data?: any)
logger.debug(category: string, message: string, data?: any) // Dev only

// Specialized logging
logger.userAction(action: string, details?: any)
logger.apiRequest(method: string, url: string, data?: any)
logger.apiResponse(method: string, url: string, status: number, duration: number, data?: any)
logger.apiError(method: string, url: string, error: any, duration?: number)
logger.navigation(from: string, to: string)

// Utility methods
logger.getLogs() // Get all logs
logger.clearLogs() // Clear log buffer
logger.exportLogs() // Export as JSON
```

### Automatic Logging

Several logging features are automatic:

1. **HTTP Interceptors** (`src/lib/http.ts`):
   - All API requests/responses logged automatically
   - Request duration tracked
   - Sensitive data (API keys) redacted

2. **Router Guards** (`src/router.ts`):
   - Navigation events logged automatically
   - Route loading errors captured

3. **Global Error Handlers** (`src/main.ts`):
   - Uncaught errors logged
   - Unhandled promise rejections logged

4. **Component Integration**:
   - User actions in code generator logged
   - Button clicks, form submissions tracked

## Security Considerations

### Sensitive Data Protection

Both backend and frontend implementations protect sensitive data:

1. **API Keys**: Automatically redacted in frontend logs
2. **User Content**: Only metadata logged (lengths, types), not full content
3. **Stack Traces**: Only included for errors, not routine operations

### Example of Data Sanitization

```typescript
// Before logging
const data = { prompt: "...", api_key: "sk-1234567890" }

// After sanitization
const sanitizedData = { prompt: "...", api_key: "[REDACTED]" }
```

## Viewing Logs

### Backend Logs

**Development (local)**:
```bash
# View live logs
tail -f /var/log/genai-portfolio/app.log

# View with grep for filtering
tail -f /var/log/genai-portfolio/app.log | grep ERROR
tail -f /var/log/genai-portfolio/app.log | grep USER_ACTION
```

**Production (Docker)**:
```bash
# Container logs (stdout)
docker compose logs -f backend

# File logs (if volume mounted)
docker compose exec backend tail -f /var/log/genai-portfolio/app.log
```

### Frontend Logs

**Browser Console**:
- Open browser DevTools (F12)
- Navigate to Console tab
- All logs appear with color-coded severity

**Programmatic Access**:
```javascript
// In browser console
import { logger } from './lib/logger'

// Get all logs
logger.getLogs()

// Export as JSON
console.log(logger.exportLogs())

// Clear logs
logger.clearLogs()
```

## Log Filtering and Analysis

### Backend Log Patterns

```bash
# Find all errors
grep ERROR /var/log/genai-portfolio/app.log

# Find specific user action
grep "\[USER_ACTION\]\[generate\]" /var/log/genai-portfolio/app.log

# Track a specific request by ID
grep "id=1699893045123-140234" /var/log/genai-portfolio/app.log

# Find slow requests (>5 seconds)
grep "duration=[5-9]\.[0-9]" /var/log/genai-portfolio/app.log
```

### Frontend Console Filtering

In browser DevTools Console:
- Use the filter box to search for specific categories
- Filter by log level (Info, Warnings, Errors)
- Use browser's search (Ctrl+F) to find specific messages

## Troubleshooting

### Backend Issues

**Problem**: Logs not appearing in file
**Solution**: Check permissions on `/var/log/genai-portfolio` directory

**Problem**: Too many logs
**Solution**: Adjust log level in `app/main.py`: `logger.setLevel(logging.WARNING)`

### Frontend Issues

**Problem**: Logs not appearing in console
**Solution**: Check browser console is open and not filtered

**Problem**: Too verbose in production
**Solution**: DEBUG logs only appear in development mode

## Future Enhancements

Potential improvements for the logging system:

1. **Remote Logging**: Send frontend logs to backend/analytics service
2. **Log Aggregation**: Integration with tools like Elasticsearch, Splunk
3. **Metrics Dashboard**: Real-time visualization of log data
4. **Structured Logging**: JSON-formatted logs for better parsing
5. **User Session Tracking**: Associate logs with user sessions
6. **Performance Metrics**: Track and log performance data
7. **Log Sampling**: Sample high-volume logs in production

## Best Practices

1. **Don't log sensitive data**: Never log passwords, tokens, full API keys
2. **Log context**: Include relevant context (request IDs, user actions)
3. **Use appropriate levels**: ERROR for failures, INFO for actions, DEBUG for details
4. **Be consistent**: Use established categories and patterns
5. **Keep it readable**: Format messages clearly and consistently
6. **Monitor log size**: Ensure rotation and retention policies are working

## References

- Backend Logger: `backend/app/core/logger.py`
- Backend Middleware: `backend/app/main.py` (RequestLoggingMiddleware)
- Backend Routes: `backend/app/api/routes.py`
- Frontend Logger: `frontend/src/lib/logger.ts`
- Frontend HTTP: `frontend/src/lib/http.ts`
- Frontend Router: `frontend/src/router.ts`
- Frontend Main: `frontend/src/main.ts`
