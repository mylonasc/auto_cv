"""Application factory: imports define routes; lifespan constructs runtime stores."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.paths import StoragePaths
from services.application import ApplicationServices, OperationError
from api import cv_jobs, config, models, cv_data, submissions
from src.outcomes import StageFailure


def create_app(*, paths=None, services=None):
    paths = paths or (services.paths if services is not None else StoragePaths.from_env())

    @asynccontextmanager
    async def lifespan(app):
        app.state.services = services if services is not None else ApplicationServices(paths)
        app.state.services.jobs.recover_interrupted()
        try:
            yield
        finally:
            await app.state.services.runner.shutdown()

    app = FastAPI(title="CV Customizer API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    for router in (cv_jobs.router, config.router, models.router, cv_data.router, submissions.router):
        app.include_router(router)

    @app.exception_handler(OperationError)
    async def operation_error(request: Request, error: OperationError):
        return JSONResponse(status_code=error.status, content={"detail": error.message})

    @app.exception_handler(StageFailure)
    async def stage_error(request: Request, error: StageFailure):
        return JSONResponse(status_code=502, content={"detail": str(error)})

    @app.exception_handler(FileNotFoundError)
    async def missing(request: Request, error: FileNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "Record or source file not found"})

    @app.exception_handler(FileExistsError)
    async def exists(request: Request, error: FileExistsError):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @app.exception_handler(ValueError)
    async def conflict(request: Request, error: ValueError):
        return JSONResponse(status_code=409, content={"detail": f"Data requires resolution: {error}"})

    @app.get("/")
    async def root():
        return {"name": "CV Customizer API", "version": "1.0.0", "status": "running"}

    @app.get("/v1/health")
    async def health():
        return {"status": "healthy"}

    app.mount("/artifacts", StaticFiles(directory=str(paths.artifacts), check_dir=False), name="artifacts")
    return app
