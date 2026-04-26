from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

WorkMode = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full-time", "contract", "internship"]
Seniority = Literal["junior", "mid", "senior", "staff"]
ApplicationStatus = Literal["submitted"]


@dataclass(slots=True)
class SalaryRange:
    currency: str
    min: int
    max: int


@dataclass(slots=True)
class JobRecord:
    id: str
    title: str
    company: str
    location: str
    work_mode: WorkMode
    employment_type: EmploymentType
    seniority: Seniority
    salary_range: SalaryRange
    keywords: list[str]
    summary: str
    description: str
    posted_at: str
    application_url: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ApplicationRecord:
    id: str
    job_id: str
    applicant_name: str
    applicant_email: str
    resume_url: str
    cover_note: str
    status: ApplicationStatus
    submitted_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def job_from_dict(payload: dict[str, object]) -> JobRecord:
    salary_range = payload["salary_range"]
    assert isinstance(salary_range, dict)
    return JobRecord(
        id=str(payload["id"]),
        title=str(payload["title"]),
        company=str(payload["company"]),
        location=str(payload["location"]),
        work_mode=payload["work_mode"],  # type: ignore[arg-type]
        employment_type=payload["employment_type"],  # type: ignore[arg-type]
        seniority=payload["seniority"],  # type: ignore[arg-type]
        salary_range=SalaryRange(
            currency=str(salary_range["currency"]),
            min=int(salary_range["min"]),
            max=int(salary_range["max"]),
        ),
        keywords=[str(item) for item in payload["keywords"]],
        summary=str(payload["summary"]),
        description=str(payload["description"]),
        posted_at=str(payload["posted_at"]),
        application_url=str(payload["application_url"]),
    )


def application_from_dict(payload: dict[str, object]) -> ApplicationRecord:
    return ApplicationRecord(
        id=str(payload["id"]),
        job_id=str(payload["job_id"]),
        applicant_name=str(payload["applicant_name"]),
        applicant_email=str(payload["applicant_email"]),
        resume_url=str(payload["resume_url"]),
        cover_note=str(payload["cover_note"]),
        status=payload["status"],  # type: ignore[arg-type]
        submitted_at=str(payload["submitted_at"]),
    )
