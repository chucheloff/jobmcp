from __future__ import annotations

from app.repository import JobRepository
from app.seed_data import MOCK_JOBS


async def test_save_jobs_replaces_stale_records(fake_valkey_client, stale_job_payload) -> None:
    repository = JobRepository("redis://unused", "test-jobmcp")
    repository._client = fake_valkey_client
    fake_valkey_client.sets["test-jobmcp:jobs"] = {"job-stale"}
    fake_valkey_client.values["test-jobmcp:job:job-stale"] = stale_job_payload

    await repository.save_jobs(MOCK_JOBS[:2])

    assert "test-jobmcp:job:job-stale" not in fake_valkey_client.values
    jobs = await repository.list_jobs()
    assert [job.id for job in jobs] == ["job-001", "job-002"]


async def test_search_jobs_filters_and_sorts_results(seeded_repository) -> None:
    jobs = await seeded_repository.search_jobs(
        query="engineer",
        work_mode="remote",
        keywords=["typescript"],
        min_salary=90000,
        limit=5,
    )

    assert [job.id for job in jobs] == ["job-001", "job-004"]
    assert jobs[0].posted_at > jobs[1].posted_at


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
    assert application.status == "submitted"
    assert [item.id for item in applications] == [application.id]


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
