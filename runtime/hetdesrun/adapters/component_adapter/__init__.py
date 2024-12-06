import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError

from hetdesrun.adapters.exceptions import AdapterHandlingException
from hetdesrun.backend.execution import TrafoExecutionInputValidationError, nested_nodes
from hetdesrun.models.code import CodeModule
from hetdesrun.models.component import ComponentRevision
from hetdesrun.models.data_selection import FilteredSink, FilteredSource
from hetdesrun.models.run import ConfigurationInput, WorkflowExecutionInput
from hetdesrun.models.wiring import InputWiring, WorkflowWiring
from hetdesrun.persistence.models.io import (
    InputType,
    IOInterface,
    TransformationInput,
    TransformationOutput,
)
from hetdesrun.persistence.models.transformation import TransformationRevision
from hetdesrun.persistence.models.workflow import WorkflowContent
from hetdesrun.runtime.logging import execution_context_filter
from hetdesrun.runtime.service import runtime_service
from hetdesrun.utils import State, Type

logger = logging.getLogger(__name__)


def to_component_trafo_rev(
    component_revision: ComponentRevision, code_module: CodeModule
) -> TransformationRevision:
    """Reconstruct a trafo rev from component rev and code module

    The runtime does never get transformation revisions but only broken down
    stuff that only contain what is necessary to execute them.

    For the component adapter in the runtime, in order to handle proper wrapping as workflow
    and things that prepare_execution_input normally does in the backend, we need a
    TransformationRevision object to reuse the respective methods.

    This function recreates a TransformationRevision (stub with some info missing) from
    the ComponentRevision and CodeModule
    """
    return TransformationRevision(
        id=component_revision.uuid,
        revision_group_id=UUID(
            "00000000-1111-0000-1111-000000000000"
        ),  # unfortunately we don't have that info.
        # Therefore we use a fixed (obviously wrong) uuid here for revision_group_id
        name=component_revision.name,
        description=(
            "TRAFO REV "
            + component_revision.name
            + " ("
            + component_revision.tag
            + ") "
            + " REGENERATED FOR COMPONENT ADAPTER"
        ),
        category="UNKNOWN CATEGORY SINCE REGENERATED FOR COMPONENT ADAPTER",
        version_tag=component_revision.tag,
        disabled_timestamp=None,
        released_timestamp=None,
        state=State.DRAFT,
        type=Type.COMPONENT,
        documentation="UNKNOWN DOCUMENTATION SINCE REGENERATED FOR COMPONENT ADAPTER",
        content=code_module.code,
        io_interface=IOInterface(
            inputs=[
                TransformationInput(
                    id=comp_inp.id,
                    name=comp_inp.name,
                    data_type=comp_inp.type,
                    type=(InputType.OPTIONAL if comp_inp.default else InputType.REQUIRED),
                    value=comp_inp.default_value,
                )
                for comp_inp in component_revision.inputs
            ],
            outputs=[
                TransformationOutput(
                    id=comp_outp.id,
                    name=comp_outp.name,
                    data_type=comp_outp.type,
                )
                for comp_outp in component_revision.outputs
            ],
        ),
        test_wiring=WorkflowWiring(),
        release_wiring=None,
    )


def wf_exec_input_from_component_trafo_revision(
    component_trafo_rev: TransformationRevision,
    wiring: WorkflowWiring | None,
    run_pure_plot_operators=True,
    job_id=None,
) -> WorkflowExecutionInput:
    tr_workflow = component_trafo_rev.wrap_component_in_tr_workflow()
    assert isinstance(  # noqa: S101
        tr_workflow.content, WorkflowContent
    )  # hint for mypy

    nested_transformations = {tr_workflow.content.operators[0].id: component_trafo_rev}
    nested_components = {
        tr.id: tr for tr in nested_transformations.values() if tr.type == Type.COMPONENT
    }

    workflow_node = tr_workflow.to_workflow_node(
        operator_id=uuid4(),
        sub_nodes=nested_nodes(tr_workflow, nested_transformations),
    )

    try:
        execution_input = WorkflowExecutionInput(
            code_modules=(
                [tr_component.to_code_module() for tr_component in nested_components.values()]
            ),
            components=(
                [component.to_component_revision() for component in nested_components.values()]
            ),
            workflow=workflow_node,
            configuration=ConfigurationInput(
                name=str(tr_workflow.id),
                run_pure_plot_operators=run_pure_plot_operators,
            ),
            workflow_wiring=wiring if wiring is not None else component_trafo_rev.test_wiring,
            job_id=uuid4() if job_id is None else job_id,
            trafo_id=component_trafo_rev.id,
        )
    except ValidationError as e:
        raise TrafoExecutionInputValidationError(e) from e

    return execution_input


def workflow_wiring_from_filters(filtered_source: FilteredSource) -> WorkflowWiring:
    """Converts the filters from a component adapter source to a wiring

    This wiring can then be used to run the referenced component.
    """
    return WorkflowWiring(
        input_wirings=[
            InputWiring(
                workflow_input_name=filter_key,
                adapter_id="direct_provisioning",
                filters={"value": filter_val},
                type=filtered_source.type,  # TODO: makes this sense? Is this actually used?
            )
            for filter_key, filter_val in filtered_source.filters.items()
        ],
        # unwired outputs default to direct_provisioning, so we do not need to set this here:
        output_wirings=[],
    )


async def load_data(
    wf_input_name_to_filtered_source_mapping_dict: dict[str, FilteredSource],
    adapter_key: str,  # noqa: ARG001
) -> dict[str, Any]:
    code_modules = execution_context_filter.get_value("current_code_modules")
    component_revisions = execution_context_filter.get_value("current_components")

    code_modules_by_id = {str(code_module.uuid): code_module for code_module in code_modules}
    component_revisions_by_id = {str(comp_rev.uuid): comp_rev for comp_rev in component_revisions}

    fetch_tasks = {}
    try:
        async with asyncio.TaskGroup() as tg:
            # The await is implicit when the context manager exits.
            for (
                inp_name,
                filtered_component_adapter_src,
            ) in wf_input_name_to_filtered_source_mapping_dict.items():
                # obtain component revision and code module
                referenced_component_id = (
                    ref_key
                    if (ref_key := filtered_component_adapter_src.ref_key) is not None
                    else filtered_component_adapter_src.ref_id
                )
                if referenced_component_id not in component_revisions_by_id:
                    raise ValueError(f"ComponentRevision {referenced_component_id} NOT PRESENT")

                code_module_uuid = str(
                    component_revisions_by_id[referenced_component_id].code_module_uuid
                )
                if code_module_uuid not in code_modules_by_id:
                    raise ValueError(f"CODE MODULE {code_module_uuid} NOT PRESENT")

                component_rev = component_revisions_by_id[str(referenced_component_id)]

                if len(component_rev.outputs) != 1:
                    raise ValueError(
                        "Component used for component adapter as source does "
                        "not have exactly one output"
                    )

                code_module = code_modules_by_id[str(code_module_uuid)]

                component_trafo_rev = to_component_trafo_rev(component_rev, code_module)

                wf_exec_input = wf_exec_input_from_component_trafo_revision(
                    component_trafo_rev,
                    workflow_wiring_from_filters(filtered_component_adapter_src),
                )

                task = tg.create_task(runtime_service(runtime_input=wf_exec_input))
                fetch_tasks[inp_name] = task

        # tasks are awaited when leaving async with context of task group
        # since they are actual task, they get their own execution context etc.
    except Exception as e:
        msg = f"Failed loading data via component adapter. Error was {str(e)}"
        logger.error(msg)
        raise AdapterHandlingException("Failed loading data via component adapter: ") from e

    # get actual results and return

    return {
        inp_name: next(iter(task.result().output_results_by_output_name.values()), None)
        # has exactly one output, this gets this only value of the dict
        for inp_name, task in fetch_tasks.items()
    }


async def send_data(
    wf_output_name_to_filtered_sink_mapping_dict: dict[str, FilteredSink],
    wf_output_name_to_value_mapping_dict: dict[str, Any],
    adapter_key: str,  # noqa: ARG001
) -> dict[str, Any]:
    raise NotImplementedError("component adapter send not implemented yet.")
