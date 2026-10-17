"""Compatibility Uvicorn entry point. Runtime initialization belongs to lifespan."""

from core.paths import ensure_project_root_on_path, ensure_backend_root_on_path

ensure_project_root_on_path()
ensure_backend_root_on_path()

from application import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
