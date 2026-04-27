from __future__ import annotations

from starlette.requests import Request

from app import main
from app.config import Settings
from app.seed_data import MOCK_COMPANIES, MOCK_JOBS


async def test_search_jobs_tool_returns_matches(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    result = await main.search_jobs(query="agent", work_mode="remote")

    assert result["total"] >= 1
    assert "job-001" in {job["id"] for job in result["jobs"]}


async def test_get_job_tool_returns_company_profile_from_job_company_id(
    monkeypatch,
    seeded_repository,
) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    result = await main.get_job("job-001")

    assert result["found"] is True
    assert result["job"]["id"] == "job-001"
    assert result["job"]["company_id"] == "company-northstar"
    assert result["company"]["id"] == "company-northstar"
    assert result["company"]["name"] == "Northstar Labs"
    assert result["company"]["postal_code"] == "78701"
    assert result["company"]["phone"] == "+1-512-555-0194"


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


async def test_submit_application_returns_number_and_status_can_be_checked(
    monkeypatch,
    seeded_repository,
) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    submit_result = await main.submit_mock_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
    )
    application_number = submit_result["application_number"]
    status_result = await main.get_application_status(application_number)

    assert submit_result["submitted"] is True
    assert application_number == submit_result["application"]["id"]
    assert status_result["found"] is True
    assert status_result["application_number"] == application_number
    assert status_result["status"] == "submitted"


async def test_application_status_tool_can_manually_update_status(
    monkeypatch,
    seeded_repository,
) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    submit_result = await main.submit_mock_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
    )
    update_result = await main.update_application_status(
        submit_result["application_number"],
        "positive",
    )

    assert update_result["updated"] is True
    assert update_result["status"] == "positive"
    assert update_result["application"]["decided_at"] is not None


async def test_company_tools_manage_company_profiles(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    update_result = await main.update_company(
        "company-northstar",
        size="201-500",
        headquarters="Denver, CO",
        address_line1="100 Market St",
        postal_code="80202",
        phone="+1-303-555-0100",
        short_history="Relocated the mock headquarters for testing.",
    )
    get_result = await main.get_company("company-northstar")

    assert update_result["updated"] is True
    assert get_result["company"]["size"] == "201-500"
    assert get_result["company"]["headquarters"] == "Denver, CO"
    assert get_result["company"]["address_line1"] == "100 Market St"
    assert get_result["company"]["postal_code"] == "80202"
    assert get_result["company"]["phone"] == "+1-303-555-0100"
    assert get_result["company"]["short_history"] == "Relocated the mock headquarters for testing."


async def test_get_company_jobs_tool_returns_company_listings(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)

    result = await main.get_company_jobs("company-northstar")

    assert result["found"] is True
    assert result["total"] == 3
    assert {job["id"] for job in result["jobs"]} == {"job-001", "job-002", "job-003"}


async def test_reset_mock_data_tool_reseeds_catalog(monkeypatch, seeded_repository) -> None:
    monkeypatch.setattr(main, "repository", seeded_repository)
    await seeded_repository.clear_mock_data()

    result = await main.reset_mock_data(scope="all")

    assert result["reset"] is True
    assert result["companies_seeded"] == len(MOCK_COMPANIES)
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
