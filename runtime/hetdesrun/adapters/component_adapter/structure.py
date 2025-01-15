import logging
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from hdutils import DataType
from hetdesrun.adapters.component_adapter.config import get_component_adapter_config
from hetdesrun.adapters.component_adapter.models import (
    ComponentAdapterStructureSink,
    ComponentAdapterStructureSource,
    StructureResponse,
    StructureThingNode,
)
from hetdesrun.adapters.exceptions import AdapterHandlingException
from hetdesrun.adapters.generic_rest.external_types import ExternalType
from hetdesrun.models.code import ValidStr
from hetdesrun.persistence.dbservice.revision import (
    get_distinct_categories,
    select_multiple_transformation_revisions,
)
from hetdesrun.persistence.models.io import InputType
from hetdesrun.persistence.models.transformation import TransformationRevision
from hetdesrun.utils import State, Type

# need DataType (component output) to ExternalType mapping

data_type_to_external_type_map = {
    DataType.Integer: ExternalType.METADATA_INT,
    DataType.Float: ExternalType.METADATA_FLOAT,
    DataType.String: ExternalType.METADATA_STR,
    DataType.DataFrame: ExternalType.DATAFRAME,
    DataType.Series: ExternalType.TIMESERIES_NUMERIC,
    DataType.MultiTSFrame: ExternalType.MULTITSFRAME,
    DataType.Boolean: ExternalType.METADATA_BOOLEAN,
    DataType.Any: ExternalType.METADATA_ANY,
    DataType.PlotlyJson: ExternalType.PLOTLYJSON,
}

logger = logging.getLogger(__name__)


def extract_filters_from_component(
    component: TransformationRevision, as_sink: bool = False
) -> dict[str, dict[str, Any]]:
    """Maps inputs to filters

    * All inputs but the single "data" input for sink components
    * "timestampTo" and "timestampFrom" are not explicitely added as filters
      since they are automatically
    added by frontend for respective types

    All filters extracted this way get the "free_text" type since currently there are no other
    choosable filter types.

    """
    component_inputs = component.io_interface.inputs
    # InputTypeMixIn
    # IO
    # TransformationInput
    return {
        inp.name: {
            "name": inp.name,
            "type": "free_text",
            "required": (inp.type is InputType.REQUIRED),  # not required means optional
            "default_value": inp.value,  # None if not set
        }
        for inp in component_inputs
        if (not as_sink or inp.name == "data")
        and (inp.name not in {"timestampFrom", "timestampTo"})
        and inp.name is not None
    }


def get_allowed_component_states(allow_disabled: bool = True) -> list[State]:
    return (
        [State.RELEASED, State.DRAFT]
        if get_component_adapter_config().allow_draft_components
        else [State.RELEASED]
    ) + ([State.DISABLED] if allow_disabled else [])


def get_all_component_sources(
    ids: list[UUID] | None = None,
    allowed_categories: list[ValidStr] | None = None,
    with_disabled_components: bool = False,
) -> list[ComponentAdapterStructureSource]:
    """Obtains components appliable as comp. sources and wraps them as sources

    if allowed_categories is None, all categories are allowed. Else this restricts which
    categories are allowed and only returns appliable comp. sources with one of these
    categories.
    """
    try:
        components = select_multiple_transformation_revisions(
            type=Type.COMPONENT,
            categories=allowed_categories,
            ids=ids,
            states=get_allowed_component_states(allow_disabled=with_disabled_components),
        )
    except Exception as e:
        msg = (
            f"Could not obtain components from database for component adapter. Error was:\n{str(e)}"
        )
        logger.error(msg)
        raise e

    return sorted(
        [
            ComponentAdapterStructureSource(
                type=(
                    ext_type := data_type_to_external_type_map[
                        component.io_interface.outputs[0].data_type
                    ]
                ),
                id=str(component.id)
                if not (is_metadatum := str(ext_type).lower().startswith("metadata"))
                else component.category,
                thingNodeId=component.category,
                name=component.name + " (" + component.version_tag + ")",
                path=component.category + "/" + component.name + " (" + component.version_tag + ")",
                metadataKey=str(component.id) if is_metadatum else None,
                filters=extract_filters_from_component(component),
            )
            for component in components
            if len(component.io_interface.outputs) == 1  # excatly one output
        ],
        key=lambda x: x.name,
    )


def validate_source_trafos_for_component_adapter(
    transformation_revisions: list[TransformationRevision], allow_disabled: bool = True
) -> None:
    """Validate trafos as component sources

    raises ValueError if some condition from configuration or concerning io is
    not true for some trafo.
    """
    allowed_states = get_allowed_component_states(allow_disabled=allow_disabled)

    allowed_source_categories = get_component_adapter_config().allowed_source_categories

    if allowed_source_categories is None:  # noqa: SIM108 # explicitely for mypy
        allowed_cats = None
    else:
        allowed_cats = list(allowed_source_categories)

    for trafo in transformation_revisions:
        if not trafo.type is Type.COMPONENT:
            msg = (
                f"Tranformation {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                " is not a component. Component adapter can only use components."
            )
            raise ValueError(msg)

        if trafo.state not in allowed_states:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has state {trafo.state} which is not allowed. Allowed states are"
                f" {allowed_states}."
            )
            raise ValueError(msg)

        if allowed_cats is not None and trafo.category not in allowed_cats:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has category {trafo.category} which is not allowed for component sources."
                f" Allowed categories for component sources are {allowed_cats}."
            )
            raise ValueError(msg)

        if len(trafo.io_interface.outputs) != 1:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has more than one output which is not allowed for component sources."
                " Component sources need exactly one output."
            )
            raise ValueError(msg)


def validate_sink_trafos_for_component_adapter(
    transformation_revisions: list[TransformationRevision], allow_disabled: bool = True
) -> None:
    """Validate trafos as component sinks

    raises ValueError if some condition from configuration or concerning io is
    not true for some trafo.
    """
    allowed_states = get_allowed_component_states(allow_disabled=allow_disabled)

    allowed_sink_categories = get_component_adapter_config().allowed_sink_categories

    if allowed_sink_categories is None:  # noqa: SIM108 # explicitely for mypy
        allowed_cats = None
    else:
        allowed_cats = list(allowed_sink_categories)

    for trafo in transformation_revisions:
        if not trafo.type is Type.COMPONENT:
            msg = (
                f"Tranformation {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                " is not a component. Component adapter can only use components."
            )
            raise ValueError(msg)

        if trafo.state not in allowed_states:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has state {trafo.state} which is not allowed. Allowed states are"
                f" {allowed_states}."
            )
            raise ValueError(msg)

        if allowed_cats is not None and trafo.category not in allowed_cats:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has category {trafo.category} which is not allowed for component sinks."
                f" Allowed categories for component sinks are {allowed_cats}."
            )
            raise ValueError(msg)

        if not "data" in [trafo_inp.name for trafo_inp in trafo.io_interface.inputs]:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has no input named 'data' which is not allowed for component sinks."
                " Component sinks always need a 'data' input."
            )
            raise ValueError(msg)

        if len(trafo.io_interface.outputs) != 0:
            msg = (
                f"Component {trafo.name} ({trafo.version_tag}) with id {trafo.id}"
                f" has outputs which is not allowed for component sinks."
                " Component sinks only have inputs."
            )
            raise ValueError(msg)


def get_structure(parent_id: str | None = None) -> StructureResponse:
    allowed_source_categories = get_component_adapter_config().allowed_source_categories
    allowed_sink_categories = get_component_adapter_config().allowed_sink_categories

    if parent_id is None:
        categories = sorted(
            [
                category
                for category in get_distinct_categories(types={Type.COMPONENT})
                if (
                    allowed_source_categories is None
                    or allowed_sink_categories is None
                    or category in allowed_source_categories
                    or category in allowed_sink_categories
                )
            ]
        )

        return StructureResponse(
            id="component-adapter",
            name="Component Adapter",
            thingNodes=[
                StructureThingNode(
                    id=category,
                    parentId=None,
                    name=category,
                    description=f"Components suitable as sources/sinks in category {category}",
                )
                for category in categories
            ],
            sinks=[],
            sources=[],
        )

    if (
        allowed_source_categories is None
        or allowed_sink_categories is None
        or parent_id in allowed_source_categories
        or parent_id in allowed_sink_categories
    ):
        try:
            valid_parent_id = ValidStr(parent_id)
        except ValidationError as e:
            msg = (
                f"provided parent id to component adapter is not a ValidStr."
                f" Exception was:\n{str(e)}"
            )
            logger.warning(msg)
            sources_of_category = []
        else:
            sources_of_category = get_all_component_sources(allowed_categories=[valid_parent_id])
    else:
        sources_of_category = []

    sinks_of_category: list[ComponentAdapterStructureSink] = []

    return StructureResponse(
        id="component-adapter",
        name="Component Adapter",
        thingNodes=[],
        sinks=sinks_of_category,
        sources=sources_of_category,
    )


def get_thing_node_by_id(id: str) -> StructureThingNode | None:  # noqa: A002
    allowed_source_categories = get_component_adapter_config().allowed_source_categories
    allowed_sink_categories = get_component_adapter_config().allowed_sink_categories

    if (
        allowed_source_categories is None
        or allowed_sink_categories is None
        or id in allowed_source_categories
        or id in allowed_sink_categories
    ):
        try:
            _ = ValidStr(id)
        except ValidationError as e:
            msg = (
                f"provided thing node id to component adapter is not a ValidStr."
                f" Exception was:\n{str(e)}"
            )
            logger.info(msg)
            return None

        return StructureThingNode(
            id=id,
            parentId=None,
            name=id,
            description=f"Components suitable as sources/sinks in category {id}",
        )
    return None


def get_source_by_id(source_id: str) -> ComponentAdapterStructureSource | None:
    """Get specific component adapter source by id

    Returns None if source could not be found
    """

    resulting_component_sources = get_all_component_sources(
        ids=[UUID(source_id)], with_disabled_components=True
    )  # when explicitely querying "known" sources one should be able to get deprecated ones
    # Otherwise they wouldn't work anymore. The frontend does this when loading a wiring.

    if len(resulting_component_sources) > 1:
        msg = (
            f"Found {len(resulting_component_sources)} results when looking"
            " for one component adapter source with id {source_id}"
        )
        logger.error(msg)
        raise AdapterHandlingException(msg)

    if len(resulting_component_sources) == 0:
        return None

    allowed_source_categories = get_component_adapter_config().allowed_source_categories
    if (
        allowed_source_categories is None
        or resulting_component_sources[0].thingNodeId in allowed_source_categories
    ):
        return resulting_component_sources[0]

    return None


def get_sources(filter_str: str | None = None) -> list[ComponentAdapterStructureSource]:
    """Get component sources, filterable by name

    Allow for case-insensistive filtering of the Component source name
    which includes the tag.
    """

    allowed_source_categories = get_component_adapter_config().allowed_source_categories

    if allowed_source_categories is None:  # noqa: SIM108 # explicitely for mypy
        allowed_cats = None
    else:
        allowed_cats = list(allowed_source_categories)

    return [
        component_source
        for component_source in get_all_component_sources(allowed_categories=allowed_cats)
        if filter_str is None or (filter_str.lower() in component_source.name.lower())
    ]
