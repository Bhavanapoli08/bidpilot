from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID

# ==================== AUTH ====================
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    organization_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    
    class Config:
        from_attributes = True

# ==================== ORGANIZATION ====================
class OrganizationCreate(BaseModel):
    name: str
    email: EmailStr

class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    email: str
    
    class Config:
        from_attributes = True

# ==================== TENDER ====================
class TenderUploadResponse(BaseModel):
    tender_id: UUID
    job_id: str
    status: str
    message: str

class TenderStatusResponse(BaseModel):
    tender_id: UUID
    status: str
    page_count: Optional[int] = None
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True

class TenderResponse(BaseModel):
    id: UUID
    file_name: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== ANALYSIS ====================
class TenderAnalysisResponse(BaseModel):
    tender_id: UUID
    summary: Optional[str]
    tender_value: Optional[float]
    bid_deadline: Optional[datetime]
    sector: Optional[str]
    location: Optional[str]
    eligibility_criteria: Dict[str, Any]
    required_documents: List[str]
    
    class Config:
        from_attributes = True

# ==================== SCORING ====================
class TenderScoreResponse(BaseModel):
    win_probability: float
    eligibility_score: float
    fit_score: float
    risk_level: str
    competition_intensity: str
    recommendation: str
    reasoning: List[str]
    
    class Config:
        from_attributes = True

class CompanyProfileCreate(BaseModel):
    company_name: str
    annual_turnover: float
    net_worth: float
    team_size: int
    sectors: List[str]
    operating_states: List[str]
    certifications: Dict[str, bool]
    registrations: Dict[str, str]
    years_in_business: int

class CompanyProfileResponse(BaseModel):
    id: UUID
    company_name: str
    annual_turnover: float
    team_size: int
    sectors: List[str]
    
    class Config:
        from_attributes = True

# ==================== Q&A ====================
class TenderQARequest(BaseModel):
    question: str
    top_k: int = 5

class TenderQAResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence: float

# ==================== JOB STATUS ====================
class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ==================== USAGE ====================
class UsageResponse(BaseModel):
    tier: str
    tenders_analyzed: int
    tenders_limit: int
    percent_used: float

# ==================== MONITORING / TENDER SOURCES ====================
class TenderSourceCreate(BaseModel):
    name: str
    source_type: str = "sample"
    url: Optional[str] = None
    config: Dict[str, Any] = {}
    keywords: List[str] = []
    sectors: List[str] = []
    states: List[str] = []
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_active: bool = True

class TenderSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    keywords: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    states: Optional[List[str]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_active: Optional[bool] = None

class TenderSourceResponse(BaseModel):
    id: UUID
    name: str
    source_type: str
    url: Optional[str]
    keywords: List[str]
    sectors: List[str]
    states: List[str]
    is_active: bool
    last_checked_at: Optional[datetime]
    last_error: Optional[str]

    class Config:
        from_attributes = True

class DiscoveredTenderResponse(BaseModel):
    id: UUID
    source_id: UUID
    title: str
    description: Optional[str]
    tender_value: Optional[float]
    bid_deadline: Optional[datetime]
    sector: Optional[str]
    location: Optional[str]
    url: Optional[str]
    match_score: float
    match_reasons: List[str]
    status: str
    discovered_at: datetime

    class Config:
        from_attributes = True

class ScanResult(BaseModel):
    sources_scanned: int
    new_discovered: int
    alerts_created: int

# ==================== BIDS / WORKFLOW ====================
class BidCreate(BaseModel):
    title: Optional[str] = None
    tender_id: Optional[UUID] = None
    discovered_tender_id: Optional[UUID] = None
    assigned_to_id: Optional[UUID] = None
    notes: Optional[str] = None

class BidStageUpdate(BaseModel):
    stage: str
    note: Optional[str] = None

class BidAssign(BaseModel):
    assigned_to_id: Optional[UUID] = None
    note: Optional[str] = None

class BidEventResponse(BaseModel):
    id: UUID
    event_type: str
    from_value: Optional[str]
    to_value: Optional[str]
    note: Optional[str]
    actor_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True

class BidResponse(BaseModel):
    id: UUID
    title: str
    stage: str
    tender_id: Optional[UUID]
    discovered_tender_id: Optional[UUID]
    assigned_to_id: Optional[UUID]
    tender_value: Optional[float]
    bid_deadline: Optional[datetime]
    win_probability: Optional[float]
    notes: Optional[str]
    decided_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class BidDetailResponse(BidResponse):
    events: List[BidEventResponse] = []

class CalendarEvent(BaseModel):
    bid_id: Optional[UUID]
    tender_id: Optional[UUID]
    title: str
    deadline: datetime
    stage: Optional[str]
    days_remaining: int

# ==================== NOTIFICATIONS ====================
class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: Optional[str]
    link: Optional[str]
    bid_id: Optional[UUID]
    discovered_tender_id: Optional[UUID]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True
