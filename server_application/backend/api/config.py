"""
API routes for configuration management.
"""
from fastapi import APIRouter
from models.api_models import BackendConfig

router = APIRouter(prefix="/v1/config", tags=["Configuration"])

# In-memory config store (replace with persistent storage in production)
_current_config = BackendConfig()


@router.get("/", response_model=BackendConfig)
async def get_config():
    """Get current backend configuration."""
    return _current_config


@router.put("/", response_model=BackendConfig)
async def update_config(config: BackendConfig):
    """Update backend configuration."""
    global _current_config
    _current_config = config
    return _current_config
