"""
API routes for model management.
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
import sys
import os

# Add project root to path
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', '/home/charilaos/Workspace/auto_cv')
if CV_CUSTOMIZER_ROOT not in sys.path:
    sys.path.append(CV_CUSTOMIZER_ROOT)

router = APIRouter(prefix="/v1/models", tags=["Models"])


@router.get("/available")
async def list_available_models(provider: Optional[str] = None):
    """
    List available LLM models.
    
    - **provider**: Filter by provider (ollama, google)
    """
    models = {
        "ollama": [],
        "google": []
    }
    
    # Get Ollama models
    try:
        import ollama
        ollama_models = ollama.list()
        models["ollama"] = [m.model for m in ollama_models.models]
    except Exception as e:
        print(f"Could not list Ollama models: {e}")
    
    # Google models (static list)
    models["google"] = [
        "models/gemini-2.5-flash-preview-05-20",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash"
    ]
    
    if provider:
        if provider in models:
            return {provider: models[provider]}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    return models
