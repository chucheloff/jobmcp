from __future__ import annotations

from starlette.requests import Request

from app import main
from app.config import Settings
from app.seed_data import MOCK_JOBS


async def test_search_jobs_tool_returns_matches(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    result = await main.search_jobs(query="agent", work_mode="remote")

    assert result["total"] == 1
    assert result["jobs"][0]["id"] == "job-001"


async def test_submit_mock_application_tool_handles_missing_job(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    result = await main.submit_mock_application(
        job_id="missing-job",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
    )

    assert result == {
        "submitted": False,
        "job_id": "missing-job",
        "error": "Job not found.",
    }


async def test_reset_mock_data_tool_reseeds_catalog(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)
    await seeded_repository.clear_mock_data()

    result = await main.reset_mock_data(scope="all")

    assert result["reset"] is True
    assert result["jobs_seeded"] == len(MOCK_JOBS)
    assert len(await seeded_repository.list_jobs()) == len(MOCK_JOBS)


async def test_health_route_reports_ok(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)
    monkeypatch.setattr(
        main,
        "settings",
        Settings(
            host="0.0.0.0",
            port=8000,
            mcp_path="/mcp",
            stateless_http=True,
            valkey_url="redis://valkey:6379/0",
            valkey_prefix="jobmcp",
            seed_on_startup=True,
        ),
    )

    scope = {"type": "http", "method": "GET", "path": "/health", "headers": []}
    request = Request(scope)
    response = await main.health(request)

    assert response.status_code == 200
    assert b'"status":"ok"' in response.body
    assert b'"stateless_http":true' in response.body
