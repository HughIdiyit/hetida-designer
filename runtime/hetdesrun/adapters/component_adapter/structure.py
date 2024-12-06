import logging
from uuid import UUID

from hdutils import DataType
from hetdesrun.adapters.component_adapter.models import (
    ComponentAdapterStructureSource,
    StructureResponse,
    StructureThingNode,
)
from hetdesrun.adapters.exceptions import AdapterHandlingException
from hetdesrun.adapters.generic_rest.external_types import ExternalType
from hetdesrun.persistence.dbservice.revision import select_multiple_transformation_revisions
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
    component: TransformationRevision, as_sink=False
) -> list[dict[str, dict]]:
    """Maps inputs to filters

    * All inputs but the single "data" input for sink components
    * "timestampTo" and "timestampFrom" are not explicitely added as filters since they are automatically
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
        if (not as_sink or inp.name == "data") and inp.name not in {"timestampFrom", "timestampTo"}
    }


def get_all_component_sources(
    ids: list[UUID] | None = None,
) -> list[ComponentAdapterStructureSource]:
    # query db for component sources
    # return list of component adapter source

    # TODO: db failure handling
    components = select_multiple_transformation_revisions(
        type=Type.COMPONENT,
        categories=["Data Sources"],
        ids=ids,
        # TODO: only state=state.RELEASED
    )

    return [
        ComponentAdapterStructureSource(
            type=(
                ext_type := data_type_to_external_type_map[
                    component.io_interface.outputs[0].data_type
                ]
            ),
            id=str(component.id)
            if not (is_metadatum := str(ext_type).lower().startswith("metadata"))
            else "base",
            thingNodeId="base",  # TODO: component.category,
            name=component.name + " (" + component.version_tag + ")",
            path=component.category + "/" + component.name + " (" + component.version_tag + ")",
            metadataKey=component.id if is_metadatum else None,
            filters=extract_filters_from_component(component),
        )
        for component in components
        if len(component.io_interface.outputs) == 1  # excatly one output
    ]


def get_structure(parent_id: str | None = None) -> StructureResponse:
    if parent_id is None:
        return StructureResponse(
            id="component-adapter",
            name="Component Adapter",
            thingNodes=[
                StructureThingNode(
                    id="base",
                    parentId=None,
                    name="Suitable Components",
                    description="Components suitable as sources/sinks",
                )
            ],
            sinks=[],
            sources=[],
        )

    if parent_id == "base":
        all_sources = get_all_component_sources()

        all_sinks = []

        return StructureResponse(
            id="component-adapter",
            name="Component Adapter",
            thingNodes=[],
            sinks=all_sinks,
            sources=all_sources,
        )
    raise AdapterHandlingException("Unknown string provided as parent_id for component adapter.")


def get_source_by_id(source_id: str) -> ComponentAdapterStructureSource:
    """Get specific component adapter source by id

    Returns None if source could not be found
    """

    resulting_component_sources = get_all_component_sources(ids=[UUID(source_id)])

    if len(resulting_component_sources) > 1:
        msg = (
            f"Found {len(resulting_component_sources)} results when looking"
            " for one component adapter source with id {source_id}"
        )
        logger.error(msg)
        raise AdapterHandlingException(msg)

    if len(resulting_component_sources) == 0:
        return None

    return resulting_component_sources[0]
