"""
CV Customizer Backend API
"""
from fastapi import FastAPI

app = FastAPI(title="CV Customizer API")

# Import routes
from api import cv_jobs, config, models

app.include_router(cv_jobs.router)
app.include_router(config.router)
app.include_router(models.router)

@app.get("/")
async def root():
    return {"message": "CV Customizer API is running"}
