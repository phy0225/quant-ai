import pytest


@pytest.mark.asyncio
async def test_create_factor_discovery_task(client):
    response = await client.post(
        "/api/v1/factors/discover",
        json={"research_direction": "focus on momentum and quality factors under high volatility"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"]
    assert payload["status"] == "completed"
    assert len(payload["recommended_factors"]) >= 1


@pytest.mark.asyncio
async def test_factor_discovery_list_and_detail(client):
    created = await client.post(
        "/api/v1/factors/discover",
        json={"research_direction": "prefer low drawdown and stable alpha factors"},
    )
    task_id = created.json()["task_id"]

    listing = await client.get("/api/v1/factors/discover")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert any(row["task_id"] == task_id for row in items)

    detail = await client.get(f"/api/v1/factors/discover/{task_id}")
    assert detail.status_code == 200
    assert detail.json()["task_id"] == task_id


@pytest.mark.asyncio
async def test_create_strategy_experiment(client):
    response = await client.post(
        "/api/v1/strategy/experiment",
        json={"base_version_id": "v1", "hypothesis": "increase quality factor weight"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["experiment_id"]
    assert payload["status"] == "completed"
    assert payload["new_version_id"]


@pytest.mark.asyncio
async def test_strategy_versions_and_experiments(client):
    await client.post(
        "/api/v1/strategy/experiment",
        json={"base_version_id": "v1", "hypothesis": "reduce turnover with smoother rebalance cadence"},
    )

    versions = await client.get("/api/v1/strategy/versions")
    assert versions.status_code == 200
    assert versions.json()["total"] >= 1
    assert any(row["version_id"] == "v1" for row in versions.json()["items"])

    experiments = await client.get("/api/v1/strategy/experiments")
    assert experiments.status_code == 200
    assert experiments.json()["total"] >= 1
