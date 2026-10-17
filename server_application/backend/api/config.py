from fastapi import APIRouter, Depends
from models.api_models import BackendConfig
from services.application import ApplicationServices
from .dependencies import get_services

router = APIRouter(prefix="/v1/config", tags=["Configuration"])


@router.get("/", response_model=BackendConfig)
async def get_config(services: ApplicationServices = Depends(get_services)):
    return services.config.model_copy(deep=True)


@router.put("/", response_model=BackendConfig)
async def update_config(config: BackendConfig, services: ApplicationServices = Depends(get_services)):
    services.config = config.model_copy(deep=True)
    return services.config
