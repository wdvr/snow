#!/bin/bash
# Startup script for Lambda Web Adapter — starts FastAPI SSE server on port 8080
exec python -m uvicorn handlers.chat_stream_handler:app --host 0.0.0.0 --port 8080
