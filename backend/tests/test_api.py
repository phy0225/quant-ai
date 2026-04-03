"""API integration tests (UTF-8 clean version)."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_ok(client):
    response = await client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


@pytest.mark.asyncio
async def test_trigger_accepts_targeted_mode(client):
    response = await client.post(
        '/api/v1/decisions/trigger',
        json={'mode': 'targeted', 'symbols': ['600519']},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'targeted'
    assert payload['status'] == 'running'


@pytest.mark.asyncio
async def test_trigger_accepts_rebalance_mode(client):
    response = await client.post(
        '/api/v1/decisions/trigger',
        json={
            'mode': 'rebalance',
            'candidate_symbols': ['600519', '300750'],
            'current_portfolio': {'000001': 0.1},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['mode'] == 'rebalance'
    assert '000001' in payload['symbols']


@pytest.mark.asyncio
async def test_get_decision_orders_returns_stock_only_rows(client, completed_rebalance_run):
    response = await client.get(f'/api/v1/decisions/{completed_rebalance_run}/orders')
    assert response.status_code == 200
    rows = response.json()
    assert all(row['symbol'].isdigit() and len(row['symbol']) == 6 for row in rows)


@pytest.mark.asyncio
async def test_create_factor_discovery_task_api(client):
    response = await client.post(
        '/api/v1/factors/discover',
        json={'research_direction': 'discover robust quality and momentum factors'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['task_id']
    assert payload['status'] == 'completed'


@pytest.mark.asyncio
async def test_create_strategy_experiment_api(client):
    response = await client.post(
        '/api/v1/strategy/experiment',
        json={'base_version_id': 'v1', 'hypothesis': 'increase quality factor weight'},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['experiment_id']
    assert payload['new_version_id']
