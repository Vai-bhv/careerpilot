from datetime import date, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Variant = Literal[
    "BI Engineering",
    "Data Analytics",
    "Automation Engineering",
    "Analytics Engineering",
    "Data Engineering",
    "AI Engineering",
]
VARIANTS = list(Variant.__args__)
Kind = Literal[
    "identity",
    "contact",
    "headline",
    "summary",
    "employment",
    "achievement",
    "project",
    "project_bullet",
    "skill",
    "education",
    "certification",
    "language",
    "other",
]
Status = Literal[
    "user_confirmed", "source_supported", "estimated", "unverified", "confidential", "not_approved"
]
Stage = Literal[
    "discovered",
    "evaluated",
    "shortlisted",
    "cv_generated",
    "awaiting_approval",
    "ready_to_apply",
    "applied",
    "recruiter_responded",
    "screening",
    "technical_interview",
    "final_interview",
    "offer_received",
    "rejected",
    "withdrawn",
    "expired",
]
PRIMARY = [
    "Power BI Developer",
    "Business Intelligence Developer",
    "BI Engineer",
    "Data Analyst",
    "BI Analyst",
    "Reporting Analyst",
    "Analytics Engineer",
    "Power Platform Developer",
    "Automation Engineer",
    "Reporting and Automation Engineer",
]
SECONDARY = [
    "Data Engineer",
    "ETL Developer",
    "Associate AI Engineer",
    "Junior AI Engineer",
    "AI Automation Engineer",
    "Junior Machine Learning Engineer",
    "Technical Solutions Engineer",
    "Integration Engineer",
    "Digital Transformation Specialist",
    "Python Developer",
    "Technical Business Analyst",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def safe_url(value):
    if not value:
        return value
    u = urlsplit(value)
    if (
        u.scheme not in {"http", "https"}
        or not u.hostname
        or u.username
        or u.password
        or "\\" in value
        or any(ord(c) <= 32 for c in value)
    ):
        raise ValueError("Enter a valid HTTP(S) address without embedded credentials")
    _ = u.port
    return value


class Preferences(Input):
    target_roles: list[Text] = Field(default_factory=lambda: PRIMARY + SECONDARY)
    locations: list[Text] = ["Prague", "Praha", "Czech Republic", "Czechia", "Česko"]
    arrangement: str | None = None
    employment_type: str | None = "full-time"
    seniorities: list[Text] = ["junior", "associate", "mid"]
    languages: list[Text] | None = None
    work_authorisation: str | None = None
    availability: str | None = None
    minimum_salary: float | None = Field(None, ge=0)
    salary_currency: str | None = None
    salary_period: str | None = None
    domains: list[Text] = []
    weights: dict[
        Literal[
            "required",
            "preferred",
            "responsibilities",
            "domain",
            "projects",
            "role",
            "location",
            "arrangement",
            "seniority",
            "employment",
            "salary",
        ],
        Annotated[float, Field(ge=0, le=100)],
    ] = {
        "required": 45,
        "preferred": 8,
        "responsibilities": 9,
        "domain": 3,
        "projects": 5,
        "role": 10,
        "location": 6,
        "arrangement": 3,
        "seniority": 4,
        "employment": 4,
        "salary": 3,
    }


class ProfileData(Input):
    name: str = Field("", max_length=200)
    contact: str = Field("", max_length=400)
    github: str = ""
    preferences: Preferences = Field(default_factory=Preferences)
    _url = field_validator("github")(safe_url)


class EvidenceData(Input):
    kind: Kind
    owner: Text
    claim: Annotated[str, StringConstraints(min_length=1, max_length=3000)]
    source: Text
    status: Status = "unverified"
    external: bool = False
    technologies: list[Text] = []
    roles: list[Text] = []
    link: str = ""
    metric: str = Field("", max_length=200)
    notes: str = Field("", max_length=2000)
    _url = field_validator("link")(safe_url)


class JobData(Input):
    title: Text
    company: Text
    description: str = Field(min_length=10, max_length=200000)
    location: Text | None = None
    url: str | None = Field(None, max_length=2000)
    apply_url: str | None = Field(None, max_length=2000)
    source: Text = "manual"
    external_id: Text | None = None
    country: Text | None = None
    arrangement: Text | None = None
    employment_type: Text | None = None
    seniority: Text | None = None
    salary_min: float | None = Field(None, ge=0)
    salary_max: float | None = Field(None, ge=0)
    currency: Text | None = None
    period: Text | None = None
    required: list[Text] | None = None
    preferred: list[Text] | None = None
    experience: Text | None = None
    education: Text | None = None
    languages: list[Text] | None = None
    work_authorisation: Text | None = None
    responsibilities: list[Text] | None = None
    benefits: list[Text] | None = None
    published: date | None = None
    expires: date | None = None
    _url = field_validator("url", "apply_url")(safe_url)

    @model_validator(mode="after")
    def check_range(self):
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("Salary range is inverted")
        return self


class Generate(Input):
    kind: Literal[
        "cv",
        "cover_letter",
        "motivation",
        "recruiter_message",
        "email_application",
        "follow_up",
        "availability",
    ] = "cv"
    language: Literal["en", "cs"] = "en"
    tone: Literal["formal", "direct"] = "formal"
    length: Literal["brief", "standard"] = "standard"
    exclude: list[int] = []
    base_version: int | None = None
    section: (
        Literal[
            "Profile",
            "Experience",
            "Projects",
            "Skills",
            "Education",
            "Certifications",
            "Languages",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def section_request(self):
        if (self.base_version is None) != (self.section is None) or (
            self.section and self.kind != "cv"
        ):
            raise ValueError("Regenerating a CV section requires a base CV version and a section")
        return self


class EvidenceApproval(Input):
    confirmed: Literal[True]
    claims: dict[int, EvidenceData] = Field(min_length=1, max_length=100)


class Confirm(Input):
    cv_id: int | None = None
    existing_cv: Text | None = None
    letter_id: int | None = None
    confirmed: Literal[True]
    method: Text = "official application page"

    @model_validator(mode="after")
    def require_cv_reference(self):
        if (self.cv_id is None) == (self.existing_cv is None):
            raise ValueError("Choose one generated CV or provide the existing CV filename")
        return self


class Tracking(Input):
    status: Stage
    notes: str = Field("", max_length=4000)
    recruiter: str = Field("", max_length=300)
    interview: date | None = None
    follow_up: date | None = None
    salary: str | None = None


class VacancyFields(BaseModel):
    country: str | None = None
    arrangement: str | None = None
    employment_type: str | None = None
    seniority: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    period: str | None = None
    required: list[str] | None = None
    preferred: list[str] | None = None
    experience: str | None = None
    education: str | None = None
    languages: list[str] | None = None
    work_authorisation: str | None = None
    responsibilities: list[str] | None = None
    benefits: list[str] | None = None
    published: date | None = None
    expires: date | None = None
    confidence: str
    possible_duplicates: list[int] = []


class VacancyView(BaseModel):
    id: int
    title: str
    company: str
    location: str | None
    url: str | None
    apply_url: str | None
    description: str
    fingerprint: str
    fields: VacancyFields
    status: Stage
    created: datetime
    checked: datetime


class EvidenceView(EvidenceData):
    id: int
    profile_id: int
    created: datetime
    conflict: bool


class MatchView(BaseModel):
    score: int = Field(ge=0, le=100)
    technical_score: int | None = Field(ge=0, le=100)
    eligibility: str
    fit: str
    recommendation: str
    matched: list[str]
    missing_required: list[str]
    missing_preferred: list[str]
    achievements: list[int]
    projects: list[int]
    variant: Variant
    concerns: list[str]
    evidence_ids: list[int]
    components: dict[str, float]
    explanation: str


class DocumentView(BaseModel):
    id: int
    created: datetime
    job_id: int
    kind: str
    snapshot: dict
    plain: str
    approved: bool


class ApplicationView(BaseModel):
    id: int
    created: datetime
    job_id: int
    status: Stage
    cv_id: int | None
    letter_id: int | None
    submitted: datetime | None
    details: dict
