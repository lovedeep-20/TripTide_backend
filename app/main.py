from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import time
import uuid
from app.core.config import settings
from app.api.endpoints import chat, search
from app.core.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize resources
    print("Starting Travel Assistant API...")
    yield
    # Shutdown: Clean up resources
    print("Shutting down Travel Assistant API...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A smart travel assistant API with function calling capabilities",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API routers
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])


# Middleware to log requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url} - RequestID: {request_id}")
    
    try:
        response = await call_next(request)
    except Exception as e:
        print(f"Request error: {str(e)}")
        raise
    
    # Calculate process time
    process_time = (time.time() - start_time) * 1000
    print(f"Request completed in {process_time:.2f}ms - Status: {response.status_code}")
    
    # Add headers
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
    response.headers["X-Request-ID"] = request_id
    
    return response

@app.get("/")
async def root():
    """Root endpoint that provides basic API information"""
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "provider": settings.DEFAULT_LLM_PROVIDER
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
