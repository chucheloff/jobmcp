from __future__ import annotations

from datetime import datetime, timedelta

from app.repository import JobRepository
from app.seed_data import MOCK_COMPANIES, MOCK_JOBS


def test_mock_jobs_have_at_least_three_openings_per_company() -> None:
    jobs_by_company = {
        company.id: [job for job in MOCK_JOBS if job.company_id == company.id]
        for company in MOCK_COMPANIES
    }

    assert len(MOCK_JOBS) >= 15
    assert all(len(jobs) >= 3 for jobs in jobs_by_company.values())
    assert all(len({job.title for job in jobs}) == len(jobs) for jobs in jobs_by_company.values())


async def test_save_jobs_appends_to_existing_records(fake_valkey_client, stale_job_payload) -> None:
    repository = JobRepository("redis://unused", "test-jobmcp")
    repository._client = fake_valkey_client
    await repository.save_companies(MOCK_COMPANIES)
    fake_valkey_client.sets["test-jobmcp:jobs"] = {"job-stale"}
    fake_valkey_client.sets["test-jobmcp:company_jobs:company-northstar"] = {"job-stale"}
    fake_valkey_client.values["test-jobmcp:job:job-stale"] = stale_job_payload

    await repository.save_jobs(MOCK_JOBS[:2])

    jobs = await repository.list_jobs()
    assert {job.id for job in jobs} == {"job-stale", "job-001", "job-002"}


async def test_search_jobs_filters_and_sorts_results(seeded_repository) -> None:
    jobs = await seeded_repository.search_jobs(
        query="engineer",
        work_mode="remote",
        skills_tags=["typescript"],
        min_salary=90000,
        limit=5,
    )

    assert [job.id for job in jobs] == ["job-001", "job-010"]
    assert jobs[0].posted_at > jobs[1].posted_at


async def test_company_jobs_are_listed_by_company_id(seeded_repository) -> None:
    jobs = await seeded_repository.list_company_jobs("company-northstar")

    assert {job.id for job in jobs} == {"job-001", "job-002", "job-003"}
    assert {job.title for job in jobs} == {
        "AI Agent Engineer",
        "Recruiting Data Engineer",
        "Product Manager, Agent Workflows",
    }


async def test_applications_can_be_created_and_listed(seeded_repository) -> None:
    application = await seeded_repository.create_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )

    applications = await seeded_repository.list_applications()

    assert application.id.startswith("app-")
    assert application.company_id == "company-northstar"
    assert application.status == "submitted"
    assert [item.id for item in applications] == [application.id]


async def test_application_status_auto_decides_after_one_hour(seeded_repository) -> None:
    application = await seeded_repository.create_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )
    submitted_at = datetime.fromisoformat(application.submitted_at)

    early_application = await seeded_repository.decide_application_if_ready(
        application.id,
        now=submitted_at + timedelta(minutes=59),
        random_value=0.05,
    )
    decided_application = await seeded_repository.decide_application_if_ready(
        application.id,
        now=submitted_at + timedelta(hours=1, seconds=1),
        random_value=0.05,
    )

    assert early_application is not None
    assert early_application.status == "submitted"
    assert decided_application is not None
    assert decided_application.status == "positive"
    assert decided_application.decided_at is not None


async def test_application_status_auto_rejects_above_positive_probability(seeded_repository) -> None:
    application = await seeded_repository.create_application(
        job_id="job-002",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )
    submitted_at = datetime.fromisoformat(application.submitted_at)

    decided_application = await seeded_repository.decide_application_if_ready(
        application.id,
        now=submitted_at + timedelta(hours=1, seconds=1),
        random_value=0.5,
    )

    assert decided_application is not None
    assert decided_application.status == "rejected"


async def test_delete_job_blocks_when_applications_exist(seeded_repository) -> None:
    await seeded_repository.create_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )

    deleted, reason = await seeded_repository.delete_job("job-001")

    assert deleted is False
    assert reason == "job_has_applications"
    assert await seeded_repository.get_job("job-001") is not None


async def test_delete_job_removes_listing_when_forced(seeded_repository) -> None:
    await seeded_repository.create_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )

    deleted, reason = await seeded_repository.delete_job("job-001", force=True)

    assert deleted is True
    assert reason is None
    assert await seeded_repository.get_job("job-001") is None
    assert [application.job_id for application in await seeded_repository.list_applications()] == ["job-001"]


async def test_clear_mock_data_removes_jobs_and_applications(seeded_repository) -> None:
    await seeded_repository.create_application(
        job_id="job-001",
        applicant_name="Test User",
        applicant_email="test@example.com",
        resume_url="https://example.com/resume.pdf",
        cover_note="Excited to apply.",
    )

    await seeded_repository.clear_mock_data()

    assert await seeded_repository.list_jobs() == []
    assert await seeded_repository.list_applications() == []
