"""
Main FastAPI application for CV Customizer.
Uses modular routers for job management, configuration, and model listing.
"""
import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Add project root to path for src imports
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
if CV_CUSTOMIZER_ROOT not in sys.path:
    sys.path.append(CV_CUSTOMIZER_ROOT)

# Add backend root to path for relative imports
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.append(BACKEND_ROOT)

from api import cv_jobs, config, models, cv_data

# Create FastAPI app
app = FastAPI(
    title="CV Customizer API",
    description="API for AI-powered CV customization based on job descriptions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cv_jobs.router)
app.include_router(config.router)
app.include_router(models.router)
app.include_router(cv_data.router)

@app.get("/")
async def root():
    """API root - returns basic info."""
    return {
        "name": "CV Customizer API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": [
            "/v1/cv-jobs/",
            "/v1/config",
            "/v1/models/available"
        ]
    }

@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

# Mount static files for artifacts if needed
artifacts_dir = Path(BACKEND_ROOT) / "artifacts"
if not artifacts_dir.exists():
    artifacts_dir.mkdir(parents=True, exist_ok=True)

app.mount("/artifacts", StaticFiles(directory=str(artifacts_dir)), name="artifacts")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
