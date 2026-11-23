"""Model catalog routes: live provider lists for the settings dropdown."""

from fastapi import APIRouter, Depends

from ..models.api_models import ModelCatalogResponse
from .dependencies import get_services

router = APIRouter(prefix="/v1/models", tags=["Models"])


@router.get("/available", response_model=ModelCatalogResponse)
async def list_available_models(refresh: bool = False, services=Depends(get_services)):
    """Provider model IDs with per-provider errors; refresh bypasses the TTL cache."""
    return await services.model_catalog.get_catalog(refresh=refresh)
