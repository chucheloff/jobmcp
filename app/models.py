from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, TypeAlias, TypedDict, cast, get_args

WorkMode = Literal["remote", "hybrid", "onsite"]
EmploymentType = Literal["full-time", "contract", "internship"]
Seniority = Literal["junior", "mid", "senior", "staff"]
ApplicationStatus = Literal["submitted", "positive", "rejected"]
SalaryPeriod = Literal["year", "hour"]
OnCallPolicy = Literal["none", "business-hours", "rotating", "24-7"]
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]
RecordPayload: TypeAlias = JsonObject


class SalaryRangePayload(TypedDict):
    currency: str
    min: int
    max: int


CompanyUpdateValue: TypeAlias = str | int | float
CompanyUpdates: TypeAlias = dict[str, CompanyUpdateValue | None]
JobUpdateValue: TypeAlias = str | int | bool | list[str] | SalaryRangePayload
JobUpdates: TypeAlias = dict[str, JobUpdateValue | None]


WORK_MODES = cast(tuple[WorkMode, ...], get_args(WorkMode))
EMPLOYMENT_TYPES = cast(tuple[EmploymentType, ...], get_args(EmploymentType))
SENIORITIES = cast(tuple[Seniority, ...], get_args(Seniority))
APPLICATION_STATUSES = cast(tuple[ApplicationStatus, ...], get_args(ApplicationStatus))
SALARY_PERIODS = cast(tuple[SalaryPeriod, ...], get_args(SalaryPeriod))
ON_CALL_POLICIES = cast(tuple[OnCallPolicy, ...], get_args(OnCallPolicy))


@dataclass(slots=True)
class CompanyRecord:
    id: str
    name: str
    description: str
    website: str
    industry: str
    headquarters: str
    size: str
    legal_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    region: str = ""
    postal_code: str = ""
    country: str = ""
    po_box: str = ""
    phone: str = ""
    contact_email: str = ""
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    founded_year: int | None = None
    short_history: str = ""

    def to_dict(self) -> RecordPayload:
        return cast(RecordPayload, asdict(self))


@dataclass(slots=True)
class SalaryRange:
    currency: str
    min: int
    max: int


@dataclass(slots=True)
class JobRecord:
    id: str
    title: str
    company_id: str
    location: str
    work_mode: WorkMode
    employment_type: EmploymentType
    seniority: Seniority
    salary_range: SalaryRange
    profession_tags: list[str]
    skills_tags: list[str]
    candidate_qualities: list[str]
    summary: str
    description: str
    posted_at: str
    application_url: str
    eligible_countries: list[str] = field(default_factory=list)
    office_cities: list[str] = field(default_factory=list)
    visa_sponsorship: bool = False
    timezone_overlap_hours: int = 0
    salary_period: SalaryPeriod = "year"
    equity_offered: bool = False
    languages_required: list[str] = field(default_factory=list)
    languages_nice_to_have: list[str] = field(default_factory=list)
    role_focus: list[str] = field(default_factory=list)
    domain_tags: list[str] = field(default_factory=list)
    on_call_policy: OnCallPolicy = "none"
    relocation_required: bool = False
    relocation_countries: list[str] = field(default_factory=list)
    deal_breaker_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> RecordPayload:
        return cast(RecordPayload, asdict(self))


@dataclass(slots=True)
class ApplicationRecord:
    id: str
    job_id: str
    company_id: str
    applicant_name: str
    applicant_email: str
    resume_url: str
    cover_note: str
    status: ApplicationStatus
    submitted_at: str
    decided_at: str | None = None

    def to_dict(self) -> RecordPayload:
        return cast(RecordPayload, asdict(self))


def _string_list(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _literal_string[T: str](value: JsonValue, allowed_values: tuple[T, ...], field_name: str) -> T:
    if isinstance(value, str) and value in allowed_values:
        return value
    raise ValueError(f"Invalid {field_name}: {value!r}")


def company_from_dict(payload: RecordPayload) -> CompanyRecord:
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    founded_year = payload.get("founded_year")
    return CompanyRecord(
        id=str(payload["id"]),
        name=str(payload["name"]),
        description=str(payload["description"]),
        website=str(payload["website"]),
        industry=str(payload["industry"]),
        headquarters=str(payload["headquarters"]),
        size=str(payload["size"]),
        legal_name=str(payload.get("legal_name", "")),
        address_line1=str(payload.get("address_line1", "")),
        address_line2=str(payload.get("address_line2", "")),
        city=str(payload.get("city", "")),
        region=str(payload.get("region", "")),
        postal_code=str(payload.get("postal_code", "")),
        country=str(payload.get("country", "")),
        po_box=str(payload.get("po_box", "")),
        phone=str(payload.get("phone", "")),
        contact_email=str(payload.get("contact_email", "")),
        location=str(payload.get("location", payload.get("headquarters", ""))),
        latitude=float(latitude) if latitude is not None else None,
        longitude=float(longitude) if longitude is not None else None,
        founded_year=int(founded_year) if founded_year is not None else None,
        short_history=str(payload.get("short_history", "")),
    )


def job_from_dict(payload: RecordPayload) -> JobRecord:
    salary_range = payload["salary_range"]
    assert isinstance(salary_range, dict)
    return JobRecord(
        id=str(payload["id"]),
        title=str(payload["title"]),
        company_id=str(payload.get("company_id", payload.get("company", ""))),
        location=str(payload["location"]),
        work_mode=_literal_string(payload["work_mode"], WORK_MODES, "work_mode"),
        employment_type=_literal_string(
            payload["employment_type"],
            EMPLOYMENT_TYPES,
            "employment_type",
        ),
        seniority=_literal_string(payload["seniority"], SENIORITIES, "seniority"),
        salary_range=SalaryRange(
            currency=str(salary_range["currency"]),
            min=int(salary_range["min"]),
            max=int(salary_range["max"]),
        ),
        profession_tags=_string_list(payload.get("profession_tags", [])),
        skills_tags=_string_list(payload.get("skills_tags", payload.get("keywords", []))),
        candidate_qualities=_string_list(payload.get("candidate_qualities", [])),
        summary=str(payload["summary"]),
        description=str(payload["description"]),
        posted_at=str(payload["posted_at"]),
        application_url=str(payload["application_url"]),
        eligible_countries=_string_list(payload.get("eligible_countries", [])),
        office_cities=_string_list(payload.get("office_cities", [])),
        visa_sponsorship=bool(payload.get("visa_sponsorship", False)),
        timezone_overlap_hours=int(payload.get("timezone_overlap_hours", 0)),
        salary_period=_literal_string(
            payload.get("salary_period", "year"),
            SALARY_PERIODS,
            "salary_period",
        ),
        equity_offered=bool(payload.get("equity_offered", False)),
        languages_required=_string_list(payload.get("languages_required", [])),
        languages_nice_to_have=_string_list(payload.get("languages_nice_to_have", [])),
        role_focus=_string_list(payload.get("role_focus", [])),
        domain_tags=_string_list(payload.get("domain_tags", [])),
        on_call_policy=_literal_string(
            payload.get("on_call_policy", "none"),
            ON_CALL_POLICIES,
            "on_call_policy",
        ),
        relocation_required=bool(payload.get("relocation_required", False)),
        relocation_countries=_string_list(payload.get("relocation_countries", [])),
        deal_breaker_tags=_string_list(payload.get("deal_breaker_tags", [])),
    )


def application_from_dict(payload: RecordPayload) -> ApplicationRecord:
    return ApplicationRecord(
        id=str(payload["id"]),
        job_id=str(payload["job_id"]),
        company_id=str(payload.get("company_id", "")),
        applicant_name=str(payload["applicant_name"]),
        applicant_email=str(payload["applicant_email"]),
        resume_url=str(payload["resume_url"]),
        cover_note=str(payload["cover_note"]),
        status=_literal_string(payload["status"], APPLICATION_STATUSES, "status"),
        submitted_at=str(payload["submitted_at"]),
        decided_at=str(payload["decided_at"]) if payload.get("decided_at") is not None else None,
    )
