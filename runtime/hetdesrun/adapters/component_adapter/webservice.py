from fastapi import HTTPException

from hetdesrun.adapters.component_adapter.models import (
    ComponentAdapterStructureSource,
    InfoResponse,
    StructureResponse,
)
from hetdesrun.adapters.component_adapter.structure import get_source_by_id, get_structure
from hetdesrun.adapters.sql_adapter import VERSION
from hetdesrun.webservice.auth_dependency import get_auth_deps
from hetdesrun.webservice.router import HandleTrailingSlashAPIRouter

component_adapter_router = HandleTrailingSlashAPIRouter(
    prefix="/adapters/component", tags=["component adapter"]
)


@component_adapter_router.get(
    "/info",
    response_model=InfoResponse,
    # no auth for info endpoint
)
async def get_info_endpoint() -> InfoResponse:
    return InfoResponse(id="component-adapter", name="Component Adapter", version=VERSION)


@component_adapter_router.get(
    "/structure",
    response_model=StructureResponse,
    dependencies=get_auth_deps(),
)
async def get_structure_endpoint(parentId: str | None = None) -> StructureResponse:
    return get_structure(parent_id=parentId)


@component_adapter_router.get(
    "/sources/{source_id:path}",
    response_model=ComponentAdapterStructureSource,
    dependencies=get_auth_deps(),
)
async def get_single_source(source_id: str) -> ComponentAdapterStructureSource:
    possible_source = get_source_by_id(source_id)

    if possible_source is None:
        raise HTTPException(
            status_code=404,
            detail="Could not find component adapter source " + source_id,
        )

    return possible_source
