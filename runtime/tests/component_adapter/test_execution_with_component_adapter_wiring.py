from unittest import mock
from uuid import UUID

import pytest

from hetdesrun.backend.execution import (
    TrafoExecutionComponentAdapterComponentsNotFound,
    execute_transformation_revision,
)
from hetdesrun.models.execution import ExecByIdInput


@pytest.mark.asyncio
@pytest.mark.usefixtures(
    "_components_for_component_adapter_tests", "_pass_through_multits_component_in_db"
)
async def test_component_source_wiring_executes_correctly():
    """Execute a trafo wired with a component adapter source"""

    exec_input = ExecByIdInput(
        id=UUID("78ee6b00-9239-4214-b9bf-a093647f33f5"),  # pass through multits
        wiring={
            "input_wirings": [
                {
                    "workflow_input_name": "input",
                    "adapter_id": "component-adapter",
                    "ref_id": "f2a39f6b-3336-44f2-8c4f-2fd0a4651dd0",
                    "filters": {
                        "timestampFrom": "2025-01-14-12:00:00+00:00",
                        "timestampTo": "2025-01-15-12:00:00+00:00",
                        "frequency": "3h",
                        "metrics": "a,b",
                        "random_seed": 42,
                        "metrics_parameters": r"{}",
                    },
                }
            ]
        },
    )

    with pytest.raises(
        TrafoExecutionComponentAdapterComponentsNotFound
    ):  # validation fails since this is a DRAFT component
        exec_result = await execute_transformation_revision(exec_input)

    # Now allow DRAFT components:
    with mock.patch(
        "hetdesrun.adapters.component_adapter.config.component_adapter_config.allow_draft_components",
        True,
    ):
        exec_result = await execute_transformation_revision(exec_input)
        assert exec_result.error is None
        multitsframe = exec_result.output_results_by_output_name["output"]
        assert len(multitsframe) > 0
