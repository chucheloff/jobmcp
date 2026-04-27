from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Literal

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.config import Settings, load_settings
from app.models import (
    ApplicationStatus,
    CompanyRecord,
    EmploymentType,
    JobRecord,
    SalaryRange,
    Seniority,
    WorkMode,
)
from app.repository import JobRepository
from app.seed_data import MOCK_COMPANIES, MOCK_JOBS

settings = load_settings()
repository = JobRepository(settings.valkey_url, settings.valkey_prefix)
mcp = FastMCP("jobmcp")


async def ensure_seed_data() -> None:
    if not settings.seed_on_startup:
        return

    has_companies = await repository.has_companies()
    has_jobs = await repository.has_jobs()
    if has_companies and has_jobs:
        return

    await repository.save_companies(MOCK_COMPANIES)
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
    profession_tags: list[str] | None = None,
    skills_tags: list[str] | None = None,
    keywords: list[str] | None = None,
    candidate_qualities: list[str] | None = None,
    min_salary: int | None = None,
    limit: int = 10,
) -> dict[str, object]:
    """Search mock job openings by title, location, salary, profession tags, and skills tags."""

    jobs = await repository.search_jobs(
        query=query,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        seniority=seniority,
        profession_tags=profession_tags,
        skills_tags=skills_tags if skills_tags is not None else keywords,
        candidate_qualities=candidate_qualities,
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
    company = await repository.get_company(job.company_id)
    return {
        "found": True,
        "job": job.to_dict(),
        "company": company.to_dict() if company else None,
    }


@mcp.tool
async def add_job(
    job_id: str,
    title: str,
    company_id: str,
    location: str,
    work_mode: WorkMode,
    employment_type: EmploymentType,
    seniority: Seniority,
    salary_currency: str,
    salary_min: int,
    salary_max: int,
    profession_tags: list[str],
    skills_tags: list[str],
    candidate_qualities: list[str],
    summary: str,
    description: str,
    posted_at: str,
    application_url: str,
) -> dict[str, object]:
    """Add a job listing for an existing company."""

    if await repository.get_company(company_id) is None:
        return {"created": False, "company_id": company_id, "error": "Company not found."}

    job = JobRecord(
        id=job_id,
        title=title,
        company_id=company_id,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        seniority=seniority,
        salary_range=SalaryRange(currency=salary_currency, min=salary_min, max=salary_max),
        profession_tags=profession_tags,
        skills_tags=skills_tags,
        candidate_qualities=candidate_qualities,
        summary=summary,
        description=description,
        posted_at=posted_at,
        application_url=application_url,
    )
    await repository.upsert_job(job)
    return {"created": True, "job": job.to_dict()}


@mcp.tool
async def update_job(
    job_id: str,
    title: str | None = None,
    company_id: str | None = None,
    location: str | None = None,
    work_mode: WorkMode | None = None,
    employment_type: EmploymentType | None = None,
    seniority: Seniority | None = None,
    salary_currency: str | None = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    profession_tags: list[str] | None = None,
    skills_tags: list[str] | None = None,
    candidate_qualities: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    posted_at: str | None = None,
    application_url: str | None = None,
) -> dict[str, object]:
    """Update fields on an existing job listing."""

    existing_job = await repository.get_job(job_id)
    if existing_job is None:
        return {"updated": False, "job_id": job_id, "error": "Job not found."}

    if company_id is not None and await repository.get_company(company_id) is None:
        return {"updated": False, "job_id": job_id, "error": "Company not found."}

    updates: dict[str, object] = {
        "title": title,
        "company_id": company_id,
        "location": location,
        "work_mode": work_mode,
        "employment_type": employment_type,
        "seniority": seniority,
        "profession_tags": profession_tags,
        "skills_tags": skills_tags,
        "candidate_qualities": candidate_qualities,
        "summary": summary,
        "description": description,
        "posted_at": posted_at,
        "application_url": application_url,
    }
    if salary_currency is not None or salary_min is not None or salary_max is not None:
        updates["salary_range"] = {
            "currency": salary_currency or existing_job.salary_range.currency,
            "min": salary_min if salary_min is not None else existing_job.salary_range.min,
            "max": salary_max if salary_max is not None else existing_job.salary_range.max,
        }

    job = await repository.update_job(job_id, updates)
    assert job is not None
    return {"updated": True, "job": job.to_dict()}


@mcp.tool
async def delete_job(job_id: str, force: bool = False) -> dict[str, object]:
    """Delete a job listing, blocking deletion when applications exist unless force is true."""

    deleted, reason = await repository.delete_job(job_id, force=force)
    if deleted:
        return {"deleted": True, "job_id": job_id}
    if reason == "job_has_applications":
        return {
            "deleted": False,
            "job_id": job_id,
            "error": "Job has applications. Use force=true to delete the listing and keep applications.",
        }
    return {"deleted": False, "job_id": job_id, "error": "Job not found."}


@mcp.tool
async def list_companies() -> dict[str, object]:
    """List company records currently stored in the mock catalog."""

    companies = await repository.list_companies()
    return {"total": len(companies), "companies": [company.to_dict() for company in companies]}


@mcp.tool
async def add_company(
    company_id: str,
    name: str,
    description: str,
    website: str,
    industry: str,
    headquarters: str,
    size: str,
    legal_name: str = "",
    address_line1: str = "",
    address_line2: str = "",
    city: str = "",
    region: str = "",
    postal_code: str = "",
    country: str = "",
    po_box: str = "",
    phone: str = "",
    contact_email: str = "",
    location: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    founded_year: int | None = None,
    short_history: str = "",
) -> dict[str, object]:
    """Add or replace a company profile."""

    company = CompanyRecord(
        id=company_id,
        name=name,
        description=description,
        website=website,
        industry=industry,
        headquarters=headquarters,
        size=size,
        legal_name=legal_name,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        region=region,
        postal_code=postal_code,
        country=country,
        po_box=po_box,
        phone=phone,
        contact_email=contact_email,
        location=location,
        latitude=latitude,
        longitude=longitude,
        founded_year=founded_year,
        short_history=short_history,
    )
    await repository.upsert_company(company)
    return {"saved": True, "company": company.to_dict()}


@mcp.tool
async def update_company(
    company_id: str,
    name: str | None = None,
    description: str | None = None,
    website: str | None = None,
    industry: str | None = None,
    headquarters: str | None = None,
    size: str | None = None,
    legal_name: str | None = None,
    address_line1: str | None = None,
    address_line2: str | None = None,
    city: str | None = None,
    region: str | None = None,
    postal_code: str | None = None,
    country: str | None = None,
    po_box: str | None = None,
    phone: str | None = None,
    contact_email: str | None = None,
    location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    founded_year: int | None = None,
    short_history: str | None = None,
) -> dict[str, object]:
    """Update fields on a company profile."""

    updates: dict[str, object] = {
        "name": name,
        "description": description,
        "website": website,
        "industry": industry,
        "headquarters": headquarters,
        "size": size,
        "legal_name": legal_name,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": city,
        "region": region,
        "postal_code": postal_code,
        "country": country,
        "po_box": po_box,
        "phone": phone,
        "contact_email": contact_email,
        "location": location,
        "latitude": latitude,
        "longitude": longitude,
        "founded_year": founded_year,
        "short_history": short_history,
    }
    company = await repository.update_company(company_id, updates)
    if company is None:
        return {"updated": False, "company_id": company_id, "error": "Company not found."}
    return {"updated": True, "company": company.to_dict()}


@mcp.tool
async def get_company(company_id: str) -> dict[str, object]:
    """Fetch one company profile by id."""

    company = await repository.get_company(company_id)
    if company is None:
        return {"found": False, "company_id": company_id, "error": "Company not found."}
    return {"found": True, "company": company.to_dict()}


@mcp.tool
async def get_company_jobs(company_id: str) -> dict[str, object]:
    """Fetch all job listings for a company."""

    company = await repository.get_company(company_id)
    if company is None:
        return {"found": False, "company_id": company_id, "error": "Company not found."}

    jobs = await repository.list_company_jobs(company_id)
    return {
        "found": True,
        "company": company.to_dict(),
        "total": len(jobs),
        "jobs": [job.to_dict() for job in jobs],
    }


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
        "application_number": application.id,
        "job": {"id": job.id, "title": job.title, "company_id": job.company_id},
        "application": application.to_dict(),
    }


@mcp.tool
async def get_application_status(application_number: str) -> dict[str, object]:
    """Fetch an application status, auto-deciding submitted applications after one hour."""

    application = await repository.decide_application_if_ready(application_number)
    if application is None:
        return {
            "found": False,
            "application_number": application_number,
            "error": "Application not found.",
        }
    return {
        "found": True,
        "application_number": application.id,
        "status": application.status,
        "application": application.to_dict(),
    }


@mcp.tool
async def update_application_status(
    application_number: str,
    status: ApplicationStatus,
) -> dict[str, object]:
    """Manually update a mock application status."""

    application = await repository.update_application_status(
        application_number,
        status,
        decided_at=datetime.now(UTC).isoformat() if status != "submitted" else None,
    )
    if application is None:
        return {
            "updated": False,
            "application_number": application_number,
            "error": "Application not found.",
        }
    return {
        "updated": True,
        "application_number": application.id,
        "status": application.status,
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
        await repository.save_companies(MOCK_COMPANIES)
        await repository.save_jobs(MOCK_JOBS)
        return {
            "reset": True,
            "scope": scope,
            "companies_seeded": len(MOCK_COMPANIES),
            "jobs_seeded": len(MOCK_JOBS),
            "applications_cleared": True,
        }

    await repository.save_companies(MOCK_COMPANIES)
    await repository.save_jobs(MOCK_JOBS)
    return {
        "reset": True,
        "scope": scope,
        "companies_seeded": len(MOCK_COMPANIES),
        "jobs_seeded": len(MOCK_JOBS),
        "applications_cleared": False,
    }


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
