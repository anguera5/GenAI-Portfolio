import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging
import os
import time
import json
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
load_dotenv()

from .core.config import get_settings
from .api.routes import router as api_router

settings = get_settings()

# Configure logging: daily rotation at UTC midnight, logs under fixed path
LOG_DIR = "/var/log/genai-portfolio"
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if module reloaded (e.g., during uvicorn reload)
if not any(isinstance(h, TimedRotatingFileHandler) for h in logger.handlers):
    log_path = os.path.join(LOG_DIR, "app.log")
    file_handler = TimedRotatingFileHandler(
        filename=log_path,
        when="midnight",
        interval=1,
        utc=True,
        backupCount=14,  # keep two weeks of logs
        encoding="utf-8",
    )
    # Name rotated files with date suffix
    file_handler.suffix = "%Y-%m-%d"

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    # Force UTC timestamps in logs
    formatter.converter = time.gmtime
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Also log to stdout for container logs
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

logger.info("Starting FastAPI app at %s", datetime.now(timezone.utc).isoformat())
app = FastAPI(title=settings.app_name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests and outgoing responses."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = f"{int(time.time() * 1000)}-{id(request)}"
        start_time = time.time()
        
        # Log incoming request
        logger.info(
            "[REQUEST] id=%s method=%s path=%s client=%s",
            request_id,
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown"
        )
        
        # Log query parameters if present
        if request.url.query:
            logger.info("[REQUEST] id=%s query_params=%s", request_id, request.url.query)
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log successful response
            logger.info(
                "[RESPONSE] id=%s status=%s duration=%.3fs",
                request_id,
                response.status_code,
                duration
            )
            
            return response
            
        except Exception as exc:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "[ERROR] id=%s method=%s path=%s duration=%.3fs error=%s",
                request_id,
                request.method,
                request.url.path,
                duration,
                str(exc),
                exc_info=True
            )
            raise


# Add logging middleware first (executes last in the middleware chain)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
