import os

from pydantic import BaseSettings, Field

from hetdesrun.models.code import ValidStr


class ComponentAdapterConfig(BaseSettings):
    active: bool = Field(
        True,
        description="Whether the adapter is active and should expose web endpoints",
        env="COMPONENT_ADAPTER_ACTIVE",
    )

    allow_draft_components: bool = Field(
        False,
        description=(
            "Whether DRAFT state components are allowed to be used both as"
            " sources or sinks for the component adapter. By default only "
            "released components are allowed."
        ),
        env="COMPONENT_ADAPTER_ALLOW_DRAFT_COMPONENTS",
    )

    allowed_source_categories: set[ValidStr] | None = Field(
        None,
        description=(
            "Which categories are components allowed to have if they are sources. "
            "Set to null to allow all."
        ),
        env="COMPONENT_ADAPTER_ALLOWED_SOURCE_CATEGORIES",
    )

    allowed_sink_categories: set[ValidStr] | None = Field(
        None,
        description=(
            "Which categories are components allowed to have if they are sources. "
            "Set to null to allow all."
        ),
        env="COMPONENT_ADAPTER_ALLOWED_SINK_CATEGORIES",
    )


environment_file = os.environ.get("HD_COMPONENT_ADAPTER_ENVIRONMENT_FILE", None)

component_adapter_config = ComponentAdapterConfig(
    _env_file=environment_file if environment_file else None  # type: ignore[call-arg]
)


def get_component_adapter_config() -> ComponentAdapterConfig:
    return component_adapter_config
