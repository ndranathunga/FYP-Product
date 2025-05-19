from fastapi import APIRouter, HTTPException, Path as FastApiPath
from typing import Optional

from backend.app.prompts.prompt_engine import prompt_engine
from backend.app.config import settings
from loguru import logger

router = APIRouter()


@router.get("/prompt/{prompt_name}", summary="Get a specific prompt template")
async def get_prompt_template_endpoint(
    prompt_name: str = FastApiPath(..., description="The name of the prompt template"),
    version: Optional[str] = None,
):
    logger.debug(f"API GET /prompt/{prompt_name}. Version: {version}")
    prompt_str = prompt_engine.get_prompt(prompt_name, version=version)
    v = version or settings.prompts.engine.default_version
    if not prompt_str:
        raise HTTPException(
            status_code=404, detail=f"Prompt '{prompt_name}' v'{v}' not found."
        )
    return {"prompt_name": prompt_name, "version": v, "template": prompt_str}
