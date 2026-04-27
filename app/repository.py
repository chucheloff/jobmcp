from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import valkey.asyncio as valkey

from app.models import (
    ApplicationRecord,
    ApplicationStatus,
    CompanyRecord,
    JobRecord,
    application_from_dict,
    company_from_dict,
    job_from_dict,
)


class JobRepository:
    def __init__(self, valkey_url: str, prefix: str) -> None:
        self._valkey_url = valkey_url
        self._prefix = prefix
        self._client: valkey.Valkey | None = None

    async def connect(self) -> None:
        if self._client is None:
            self._client = valkey.from_url(self._valkey_url, decode_responses=True)
            await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def ping(self) -> bool:
        client = self._require_client()
        result = await client.ping()
        return bool(result)

    def _require_client(self) -> valkey.Valkey:
        if self._client is None:
            raise RuntimeError("Valkey client is not connected.")
        return self._client

    def _companies_key(self) -> str:
        return f"{self._prefix}:companies"

    def _company_key(self, company_id: str) -> str:
        return f"{self._prefix}:company:{company_id}"

    def _company_jobs_key(self, company_id: str) -> str:
        return f"{self._prefix}:company_jobs:{company_id}"

    def _jobs_key(self) -> str:
        return f"{self._prefix}:jobs"

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _applications_key(self) -> str:
        return f"{self._prefix}:applications"

    def _application_key(self, application_id: str) -> str:
        return f"{self._prefix}:application:{application_id}"

    def _job_applications_key(self, job_id: str) -> str:
        return f"{self._prefix}:job_applications:{job_id}"

    async def save_companies(self, companies: list[CompanyRecord]) -> None:
        client = self._require_client()
        pipeline = client.pipeline(transaction=True)
        for company in companies:
            pipeline.sadd(self._companies_key(), company.id)
            pipeline.set(self._company_key(company.id), json.dumps(company.to_dict()))
        await pipeline.execute()

    async def upsert_company(self, company: CompanyRecord) -> CompanyRecord:
        await self.save_companies([company])
        return company

    async def update_company(self, company_id: str, updates: dict[str, object]) -> CompanyRecord | None:
        company = await self.get_company(company_id)
        if company is None:
            return None

        payload = company.to_dict()
        for field in (
            "name",
            "description",
            "website",
            "industry",
            "headquarters",
            "size",
            "legal_name",
            "address_line1",
            "address_line2",
            "city",
            "region",
            "postal_code",
            "country",
            "po_box",
            "phone",
            "contact_email",
            "location",
            "latitude",
            "longitude",
            "founded_year",
            "short_history",
        ):
            if field in updates and updates[field] is not None:
                payload[field] = updates[field]

        updated = company_from_dict(payload)
        await self.upsert_company(updated)
        return updated

    async def get_company(self, company_id: str) -> CompanyRecord | None:
        client = self._require_client()
        payload = await client.get(self._company_key(company_id))
        if not payload:
            return None
        return company_from_dict(json.loads(payload))

    async def list_companies(self) -> list[CompanyRecord]:
        client = self._require_client()
        company_ids = await client.smembers(self._companies_key())
        if not company_ids:
            return []

        payloads = await client.mget([self._company_key(company_id) for company_id in company_ids])
        companies: list[CompanyRecord] = []
        for payload in payloads:
            if payload:
                companies.append(company_from_dict(json.loads(payload)))
        return sorted(companies, key=lambda company: company.name)

    async def delete_company(self, company_id: str) -> tuple[bool, str | None]:
        client = self._require_client()
        company = await self.get_company(company_id)
        if company is None:
            return False, "company_not_found"

        job_ids = await client.smembers(self._company_jobs_key(company_id))
        if job_ids:
            return False, "company_has_jobs"

        pipeline = client.pipeline(transaction=True)
        pipeline.srem(self._companies_key(), company_id)
        pipeline.delete(self._company_key(company_id), self._company_jobs_key(company_id))
        await pipeline.execute()
        return True, None

    async def save_jobs(self, jobs: list[JobRecord]) -> None:
        for job in jobs:
            await self.upsert_job(job)

    async def upsert_job(self, job: JobRecord) -> JobRecord:
        client = self._require_client()
        if await self.get_company(job.company_id) is None:
            raise ValueError(f"Company does not exist: {job.company_id}")

        existing_job = await self.get_job(job.id)
        pipeline = client.pipeline(transaction=True)
        if existing_job is not None and existing_job.company_id != job.company_id:
            pipeline.srem(self._company_jobs_key(existing_job.company_id), job.id)

        pipeline.sadd(self._jobs_key(), job.id)
        pipeline.sadd(self._company_jobs_key(job.company_id), job.id)
        pipeline.set(self._job_key(job.id), json.dumps(job.to_dict()))
        await pipeline.execute()
        return job

    async def update_job(self, job_id: str, updates: dict[str, object]) -> JobRecord | None:
        existing_job = await self.get_job(job_id)
        if existing_job is None:
            return None

        payload = existing_job.to_dict()
        for field in (
            "title",
            "company_id",
            "location",
            "work_mode",
            "employment_type",
            "seniority",
            "salary_range",
            "profession_tags",
            "skills_tags",
            "candidate_qualities",
            "summary",
            "description",
            "posted_at",
            "application_url",
        ):
            if field in updates and updates[field] is not None:
                payload[field] = updates[field]

        updated = job_from_dict(payload)
        await self.upsert_job(updated)
        return updated

    async def list_jobs(self) -> list[JobRecord]:
        client = self._require_client()
        job_ids = await client.smembers(self._jobs_key())
        if not job_ids:
            return []

        payloads = await client.mget([self._job_key(job_id) for job_id in job_ids])
        jobs: list[JobRecord] = []
        for payload in payloads:
            if payload:
                jobs.append(job_from_dict(json.loads(payload)))
        return sorted(jobs, key=lambda job: job.posted_at, reverse=True)

    async def has_jobs(self) -> bool:
        client = self._require_client()
        return bool(await client.exists(self._jobs_key()))

    async def get_job(self, job_id: str) -> JobRecord | None:
        client = self._require_client()
        payload = await client.get(self._job_key(job_id))
        if not payload:
            return None
        return job_from_dict(json.loads(payload))

    async def list_company_jobs(self, company_id: str) -> list[JobRecord]:
        client = self._require_client()
        job_ids = await client.smembers(self._company_jobs_key(company_id))
        if not job_ids:
            return []

        payloads = await client.mget([self._job_key(job_id) for job_id in job_ids])
        jobs: list[JobRecord] = []
        for payload in payloads:
            if payload:
                jobs.append(job_from_dict(json.loads(payload)))
        return sorted(jobs, key=lambda job: job.posted_at, reverse=True)

    async def delete_job(self, job_id: str, *, force: bool = False) -> tuple[bool, str | None]:
        client = self._require_client()
        job = await self.get_job(job_id)
        if job is None:
            return False, "job_not_found"

        application_ids = await client.smembers(self._job_applications_key(job_id))
        if application_ids and not force:
            return False, "job_has_applications"

        pipeline = client.pipeline(transaction=True)
        pipeline.srem(self._jobs_key(), job_id)
        pipeline.srem(self._company_jobs_key(job.company_id), job_id)
        pipeline.delete(self._job_key(job_id))
        if force:
            pipeline.delete(self._job_applications_key(job_id))
        await pipeline.execute()
        return True, None

    async def search_jobs(
        self,
        *,
        query: str | None = None,
        location: str | None = None,
        work_mode: str | None = None,
        employment_type: str | None = None,
        seniority: str | None = None,
        profession_tags: list[str] | None = None,
        skills_tags: list[str] | None = None,
        candidate_qualities: list[str] | None = None,
        min_salary: int | None = None,
        limit: int = 10,
    ) -> list[JobRecord]:
        jobs = await self.list_jobs()
        normalized_query = query.strip().lower() if query else None
        normalized_location = location.strip().lower() if location else None
        normalized_professions = self._normalize_filter_tags(profession_tags)
        normalized_skills = self._normalize_filter_tags(skills_tags)
        normalized_qualities = self._normalize_filter_tags(candidate_qualities)
        bounded_limit = max(1, min(limit, 50))

        def matches(job: JobRecord) -> bool:
            if normalized_query:
                haystack = " ".join(
                    [
                        job.title,
                        job.summary,
                        job.description,
                        *job.profession_tags,
                        *job.skills_tags,
                        *job.candidate_qualities,
                    ]
                ).lower()
                if normalized_query not in haystack:
                    return False

            if normalized_location and normalized_location not in job.location.lower():
                return False

            if work_mode and job.work_mode != work_mode:
                return False

            if employment_type and job.employment_type != employment_type:
                return False

            if seniority and job.seniority != seniority:
                return False

            if min_salary is not None and job.salary_range.max < min_salary:
                return False

            if not self._contains_all(job.profession_tags, normalized_professions):
                return False

            if not self._contains_all(job.skills_tags, normalized_skills):
                return False

            if not self._contains_all(job.candidate_qualities, normalized_qualities):
                return False

            return True

        return [job for job in jobs if matches(job)][:bounded_limit]

    async def create_application(
        self,
        *,
        job_id: str,
        applicant_name: str,
        applicant_email: str,
        resume_url: str,
        cover_note: str,
    ) -> ApplicationRecord:
        client = self._require_client()
        job = await self.get_job(job_id)
        if job is None:
            raise ValueError(f"Job does not exist: {job_id}")

        application = ApplicationRecord(
            id=f"app-{uuid4().hex[:12]}",
            job_id=job_id,
            company_id=job.company_id,
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            resume_url=resume_url,
            cover_note=cover_note,
            status="submitted",
            submitted_at=datetime.now(UTC).isoformat(),
            decided_at=None,
        )
        pipeline = client.pipeline(transaction=True)
        pipeline.sadd(self._applications_key(), application.id)
        pipeline.sadd(self._job_applications_key(job_id), application.id)
        pipeline.set(self._application_key(application.id), json.dumps(application.to_dict()))
        await pipeline.execute()
        return application

    async def get_application(self, application_id: str) -> ApplicationRecord | None:
        client = self._require_client()
        payload = await client.get(self._application_key(application_id))
        if not payload:
            return None
        return application_from_dict(json.loads(payload))

    async def update_application_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        *,
        decided_at: str | None = None,
    ) -> ApplicationRecord | None:
        application = await self.get_application(application_id)
        if application is None:
            return None

        updated = ApplicationRecord(
            id=application.id,
            job_id=application.job_id,
            company_id=application.company_id,
            applicant_name=application.applicant_name,
            applicant_email=application.applicant_email,
            resume_url=application.resume_url,
            cover_note=application.cover_note,
            status=status,
            submitted_at=application.submitted_at,
            decided_at=decided_at if status != "submitted" else None,
        )
        client = self._require_client()
        await client.set(self._application_key(application_id), json.dumps(updated.to_dict()))
        return updated

    async def decide_application_if_ready(
        self,
        application_id: str,
        *,
        now: datetime | None = None,
        positive_probability: float = 0.1,
        random_value: float | None = None,
    ) -> ApplicationRecord | None:
        application = await self.get_application(application_id)
        if application is None or application.status != "submitted":
            return application

        checked_at = now or datetime.now(UTC)
        submitted_at = datetime.fromisoformat(application.submitted_at)
        if checked_at - submitted_at < timedelta(hours=1):
            return application

        score = random_value if random_value is not None else random.random()
        status: ApplicationStatus = "positive" if score < positive_probability else "rejected"
        return await self.update_application_status(
            application_id,
            status,
            decided_at=checked_at.isoformat(),
        )

    async def list_applications(self) -> list[ApplicationRecord]:
        client = self._require_client()
        application_ids = await client.smembers(self._applications_key())
        if not application_ids:
            return []

        payloads = await client.mget(
            [self._application_key(application_id) for application_id in application_ids]
        )
        applications: list[ApplicationRecord] = []
        for payload in payloads:
            if payload:
                applications.append(application_from_dict(json.loads(payload)))
        return sorted(applications, key=lambda item: item.submitted_at, reverse=True)

    async def clear_mock_data(self) -> None:
        client = self._require_client()
        jobs = await client.smembers(self._jobs_key())
        companies = await client.smembers(self._companies_key())
        applications = await client.smembers(self._applications_key())

        pipeline = client.pipeline(transaction=True)
        if jobs:
            pipeline.delete(
                *[self._job_key(job_id) for job_id in jobs],
                *[self._job_applications_key(job_id) for job_id in jobs],
            )
        if companies:
            pipeline.delete(
                *[self._company_key(company_id) for company_id in companies],
                *[self._company_jobs_key(company_id) for company_id in companies],
            )
        if applications:
            pipeline.delete(*[self._application_key(application_id) for application_id in applications])
        pipeline.delete(self._jobs_key(), self._companies_key(), self._applications_key())
        await pipeline.execute()

    @staticmethod
    def _normalize_filter_tags(tags: list[str] | None) -> set[str]:
        return {tag.strip().lower() for tag in (tags or []) if tag.strip()}

    @staticmethod
    def _contains_all(values: list[str], required: set[str]) -> bool:
        if not required:
            return True
        normalized_values = {value.lower() for value in values}
        return required.issubset(normalized_values)
