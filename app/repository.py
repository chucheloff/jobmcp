from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import valkey.asyncio as valkey

from app.models import ApplicationRecord, JobRecord, application_from_dict, job_from_dict


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

    def _jobs_key(self) -> str:
        return f"{self._prefix}:jobs"

    def _job_key(self, job_id: str) -> str:
        return f"{self._prefix}:job:{job_id}"

    def _applications_key(self) -> str:
        return f"{self._prefix}:applications"

    def _application_key(self, application_id: str) -> str:
        return f"{self._prefix}:application:{application_id}"

    async def save_jobs(self, jobs: list[JobRecord]) -> None:
        client = self._require_client()
        existing_job_ids = await client.smembers(self._jobs_key())
        pipeline = client.pipeline(transaction=True)
        if existing_job_ids:
            pipeline.delete(*[self._job_key(job_id) for job_id in existing_job_ids])
        pipeline.delete(self._jobs_key())

        for job in jobs:
            pipeline.sadd(self._jobs_key(), job.id)
            pipeline.set(self._job_key(job.id), json.dumps(job.to_dict()))

        await pipeline.execute()

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
        return jobs

    async def has_jobs(self) -> bool:
        client = self._require_client()
        return bool(await client.exists(self._jobs_key()))

    async def get_job(self, job_id: str) -> JobRecord | None:
        client = self._require_client()
        payload = await client.get(self._job_key(job_id))
        if not payload:
            return None
        return job_from_dict(json.loads(payload))

    async def list_companies(self) -> list[str]:
        jobs = await self.list_jobs()
        return sorted({job.company for job in jobs})

    async def search_jobs(
        self,
        *,
        query: str | None = None,
        location: str | None = None,
        work_mode: str | None = None,
        employment_type: str | None = None,
        seniority: str | None = None,
        keywords: list[str] | None = None,
        min_salary: int | None = None,
        limit: int = 10,
    ) -> list[JobRecord]:
        jobs = await self.list_jobs()
        normalized_query = query.strip().lower() if query else None
        normalized_location = location.strip().lower() if location else None
        normalized_keywords = {item.strip().lower() for item in (keywords or []) if item.strip()}
        bounded_limit = max(1, min(limit, 50))

        def matches(job: JobRecord) -> bool:
            if normalized_query:
                haystack = " ".join(
                    [job.title, job.company, job.summary, job.description, *job.keywords]
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

            if normalized_keywords:
                job_keywords = {item.lower() for item in job.keywords}
                if not normalized_keywords.issubset(job_keywords):
                    return False

            return True

        return sorted(
            (job for job in jobs if matches(job)),
            key=lambda job: job.posted_at,
            reverse=True,
        )[:bounded_limit]

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
        application = ApplicationRecord(
            id=f"app-{uuid4().hex[:12]}",
            job_id=job_id,
            applicant_name=applicant_name,
            applicant_email=applicant_email,
            resume_url=resume_url,
            cover_note=cover_note,
            status="submitted",
            submitted_at=datetime.now(UTC).isoformat(),
        )
        pipeline = client.pipeline(transaction=True)
        pipeline.sadd(self._applications_key(), application.id)
        pipeline.set(self._application_key(application.id), json.dumps(application.to_dict()))
        await pipeline.execute()
        return application

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
        applications = await client.smembers(self._applications_key())

        pipeline = client.pipeline(transaction=True)
        if jobs:
            pipeline.delete(*[self._job_key(job_id) for job_id in jobs])
        if applications:
            pipeline.delete(*[self._application_key(application_id) for application_id in applications])
        pipeline.delete(self._jobs_key(), self._applications_key())
        await pipeline.execute()
