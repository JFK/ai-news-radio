"""Tests for API endpoints."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PipelineStep, StepName, StepStatus


class TestEpisodesAPI:
    """Tests for Episode CRUD endpoints."""

    async def test_create_episode(self, client: AsyncClient):
        response = await client.post("/api/episodes", json={"title": "Test Episode"})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Episode"
        assert data["status"] == "draft"
        assert len(data["pipeline_steps"]) == 7

    async def test_list_episodes(self, client: AsyncClient):
        # Create two episodes
        await client.post("/api/episodes", json={"title": "Episode 1"})
        await client.post("/api/episodes", json={"title": "Episode 2"})

        response = await client.get("/api/episodes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["episodes"]) == 2

    async def test_list_episodes_empty(self, client: AsyncClient):
        response = await client.get("/api/episodes")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    async def test_get_episode(self, client: AsyncClient):
        create_response = await client.post("/api/episodes", json={"title": "Detail Test"})
        episode_id = create_response.json()["id"]

        response = await client.get(f"/api/episodes/{episode_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Detail Test"
        assert len(data["pipeline_steps"]) == 7

    async def test_get_episode_not_found(self, client: AsyncClient):
        response = await client.get("/api/episodes/999")
        assert response.status_code == 404


class TestPipelineAPI:
    """Tests for Pipeline step endpoints."""

    async def test_list_steps(self, client: AsyncClient):
        create_response = await client.post("/api/episodes", json={"title": "Steps Test"})
        episode_id = create_response.json()["id"]

        response = await client.get(f"/api/episodes/{episode_id}/steps")
        assert response.status_code == 200
        steps = response.json()
        assert len(steps) == 7

    async def test_approve_step(self, client: AsyncClient, session: AsyncSession):
        create_response = await client.post("/api/episodes", json={"title": "Approve Test"})
        episode_id = create_response.json()["id"]

        # Get step and set to NEEDS_APPROVAL
        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()
        step.status = StepStatus.NEEDS_APPROVAL
        await session.commit()

        response = await client.post(f"/api/steps/{step.id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    async def test_reject_step(self, client: AsyncClient, session: AsyncSession):
        create_response = await client.post("/api/episodes", json={"title": "Reject Test"})
        episode_id = create_response.json()["id"]

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()
        step.status = StepStatus.NEEDS_APPROVAL
        await session.commit()

        response = await client.post(
            f"/api/steps/{step.id}/reject",
            json={"reason": "Needs improvement"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["rejection_reason"] == "Needs improvement"

    async def test_approve_wrong_status(self, client: AsyncClient, session: AsyncSession):
        create_response = await client.post("/api/episodes", json={"title": "Wrong Status"})
        episode_id = create_response.json()["id"]

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.COLLECTION,
            )
        )
        step = result.scalar_one()

        response = await client.post(f"/api/steps/{step.id}/approve")
        assert response.status_code == 400

    async def test_run_step_invalid_name(self, client: AsyncClient):
        create_response = await client.post("/api/episodes", json={"title": "Invalid Step"})
        episode_id = create_response.json()["id"]

        response = await client.post(f"/api/episodes/{episode_id}/steps/invalid/run")
        assert response.status_code == 400


class TestStatsAPI:
    """Tests for cost statistics endpoints."""

    async def test_get_costs_empty(self, client: AsyncClient):
        response = await client.get("/api/stats/costs")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cost_usd"] == 0.0
        assert data["total_requests"] == 0
        assert data["by_provider"] == []
        assert data["by_step"] == []

    async def test_get_episode_costs_empty(self, client: AsyncClient):
        create_response = await client.post("/api/episodes", json={"title": "Cost Test"})
        episode_id = create_response.json()["id"]

        response = await client.get(f"/api/stats/costs/episodes/{episode_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["episode_id"] == episode_id
        assert data["total_cost_usd"] == 0.0
