import pytest


@pytest.mark.asyncio
async def test_access_component_adapter_info(
    open_async_test_client_for_component_adapter_tests,
) -> None:
    response = await open_async_test_client_for_component_adapter_tests.get(
        "adapters/component/info"
    )
    assert response.status_code == 200
    assert "version" in response.json()


@pytest.mark.asyncio
@pytest.mark.usefixtures("_components_for_component_adapter_tests")
async def test_component_adapter_get_structure_from_webservice(
    mocked_clean_test_db_session,
    open_async_test_client_for_component_adapter_tests,
):
    response = await open_async_test_client_for_component_adapter_tests.get(
        "/adapters/component/structure"
    )

    assert response.status_code == 200

    resp_obj = response.json()

    assert len(resp_obj["thingNodes"]) == 4

    # TODO: more tests for structure endpoint
    # TODO: test other endpoints
