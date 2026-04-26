from __future__ import annotations

import asyncio
from typing import Literal

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import Settings, load_settings
from app.models import EmploymentType, Seniority, WorkMode
from app.repository import JobRepository
from app.seed_data import MOCK_JOBS

settings = load_settings()
repository = JobRepository(settings.valkey_url, settings.valkey_prefix)
mcp = FastMCP("jobmcp")


async def ensure_seed_data() -> None:
    if settings.seed_on_startup and not await repository.has_jobs():
        await repository.save_jobs(MOCK_JOBS)


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    try:
        await repository.connect()
        valkey_ok = await repository.ping()
    except Exception as error:  # pragma: no cover - operational surface
        return JSONResponse(
            {"status": "degraded", "valkey": False, "error": str(error)},
            status_code=503,
        )

    return JSONResponse(
        {
            "status": "ok" if valkey_ok else "degraded",
            "transport": "http",
            "stateless_http": settings.stateless_http,
            "mcp_path": settings.mcp_path,
            "valkey": valkey_ok,
        }
    )


@mcp.tool
async def search_jobs(
    query: str | None = None,
    location: str | None = None,
    work_mode: WorkMode | None = None,
    employment_type: EmploymentType | None = None,
    seniority: Seniority | None = None,
    keywords: list[str] | None = None,
    min_salary: int | None = None,
    limit: int = 10,
) -> dict[str, object]:
    """Search mock job openings by title, location, work mode, salary, and keywords."""

    jobs = await repository.search_jobs(
        query=query,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        seniority=seniority,
        keywords=keywords,
        min_salary=min_salary,
        limit=limit,
    )
    return {"total": len(jobs), "jobs": [job.to_dict() for job in jobs]}


@mcp.tool
async def get_job(job_id: str) -> dict[str, object]:
    """Fetch a single mock job opening by id."""

    job = await repository.get_job(job_id)
    if job is None:
        return {"found": False, "job_id": job_id, "error": "Job not found."}
    return {"found": True, "job": job.to_dict()}


@mcp.tool
async def list_companies() -> dict[str, object]:
    """List companies currently represented in the mock catalog."""

    companies = await repository.list_companies()
    return {"total": len(companies), "companies": companies}


@mcp.tool
async def submit_mock_application(
    job_id: str,
    applicant_name: str,
    applicant_email: str,
    resume_url: str,
    cover_note: str = "",
) -> dict[str, object]:
    """Create a mock application record for a given job."""

    job = await repository.get_job(job_id)
    if job is None:
        return {"submitted": False, "job_id": job_id, "error": "Job not found."}

    application = await repository.create_application(
        job_id=job_id,
        applicant_name=applicant_name,
        applicant_email=applicant_email,
        resume_url=resume_url,
        cover_note=cover_note,
    )
    return {
        "submitted": True,
        "job": {"id": job.id, "title": job.title, "company": job.company},
        "application": application.to_dict(),
    }


@mcp.tool
async def list_mock_applications(job_id: str | None = None) -> dict[str, object]:
    """List mock applications stored in Valkey."""

    applications = await repository.list_applications()
    if job_id:
        applications = [item for item in applications if item.job_id == job_id]
    return {"total": len(applications), "applications": [item.to_dict() for item in applications]}


@mcp.tool
async def reset_mock_data(scope: Literal["jobs", "all"] = "all") -> dict[str, object]:
    """Reset the mock catalog and optionally clear mock applications."""

    if scope == "all":
        await repository.clear_mock_data()
        await repository.save_jobs(MOCK_JOBS)
        return {"reset": True, "scope": scope, "jobs_seeded": len(MOCK_JOBS), "applications_cleared": True}

    await repository.save_jobs(MOCK_JOBS)
    return {"reset": True, "scope": scope, "jobs_seeded": len(MOCK_JOBS), "applications_cleared": False}


async def run_server(app_settings: Settings) -> None:
    await repository.connect()
    await ensure_seed_data()
    try:
        await mcp.run_async(
            transport="http",
            host=app_settings.host,
            port=app_settings.port,
            path=app_settings.mcp_path,
            stateless_http=app_settings.stateless_http,
            show_banner=False,
        )
    finally:
        await repository.close()


def cli() -> None:
    asyncio.run(run_server(settings))


if __name__ == "__main__":
    cli()
