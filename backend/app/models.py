from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Enum, ForeignKey, JSON, Text, Date, LargeBinary, Table, Numeric
from sqlalchemy.orm import relationship
from app.db_types import GUID as UUID, JSONB, ARRAY
from app.database import Base
import uuid
from datetime import datetime
import enum as py_enum

# ==================== ORGANIZATIONS ====================
class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    domain = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    max_monthly_analyses = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = relationship("User", back_populates="organization")
    subscriptions = relationship("Subscription", back_populates="organization")
    tenders = relationship("Tender", back_populates="organization")
    company_profiles = relationship("CompanyProfile", back_populates="organization")
    usage_logs = relationship("UsageLog", back_populates="organization")
    tender_scores = relationship("TenderScore", back_populates="organization")
    tender_sources = relationship("TenderSource", back_populates="organization")
    discovered_tenders = relationship("DiscoveredTender", back_populates="organization")
    bids = relationship("Bid", back_populates="organization")
    notifications = relationship("Notification", back_populates="organization")

# ==================== USERS ====================
class UserRole(str, py_enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default=UserRole.MEMBER)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="users")

# ==================== SUBSCRIPTIONS ====================
class SubscriptionTier(str, py_enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class SubscriptionStatus(str, py_enum.Enum):
    ACTIVE = "active"
    PAYMENT_FAILED = "payment_failed"
    HALTED = "halted"
    CANCELED = "canceled"

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    razorpay_subscription_id = Column(String(255), nullable=True)
    razorpay_customer_id = Column(String(255), nullable=True)
    tier = Column(String(50), default=SubscriptionTier.FREE)
    status = Column(String(50), default=SubscriptionStatus.ACTIVE)
    price_per_month = Column(Numeric(10, 2), default=0)
    current_cycle_start = Column(DateTime, default=datetime.utcnow)
    current_cycle_end = Column(DateTime, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="subscriptions")

# ==================== TENDERS ====================
class TenderStatus(str, py_enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Tender(Base):
    __tablename__ = "tenders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    company_profile_id = Column(UUID(as_uuid=True), ForeignKey("company_profiles.id"), nullable=True)
    file_name = Column(String(255), nullable=False)
    s3_key = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_hash = Column(String(255), nullable=True)
    page_count = Column(Integer, nullable=True)
    is_scanned = Column(Boolean, default=False)
    status = Column(String(50), default=TenderStatus.PENDING)
    job_id = Column(String(255), nullable=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="tenders")
    analysis = relationship("TenderAnalysis", back_populates="tender", uselist=False)
    scores = relationship("TenderScore", back_populates="tender")

# ==================== TENDER ANALYSIS ====================
class TenderAnalysis(Base):
    __tablename__ = "tender_analyses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    summary = Column(Text, nullable=True)
    tender_value = Column(Numeric(15, 2), nullable=True)
    bid_deadline = Column(DateTime, nullable=True)
    sector = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    eligibility_criteria = Column(JSONB, default={})
    required_documents = Column(JSONB, default={})
    penalty_clauses = Column(JSONB, default={})
    key_dates = Column(JSONB, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tender = relationship("Tender", back_populates="analysis")

# ==================== TENDER SCORES ====================
class TenderScore(Base):
    __tablename__ = "tender_scores"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=False)
    company_profile_id = Column(UUID(as_uuid=True), ForeignKey("company_profiles.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    win_probability = Column(Float, default=0.0)
    eligibility_score = Column(Float, default=0.0)
    fit_score = Column(Float, default=0.0)
    risk_level = Column(String(50), default="medium")
    risk_score = Column(Float, default=0.0)
    competition_intensity = Column(String(50), default="medium")
    recommendation = Column(String(50), default="skip")
    factors = Column(JSONB, default={})
    reasoning = Column(JSONB, default=[])
    user_feedback = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tender = relationship("Tender", back_populates="scores")
    company_profile = relationship("CompanyProfile", back_populates="tender_scores")
    organization = relationship("Organization", back_populates="tender_scores")

# ==================== COMPANY PROFILES ====================
class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    company_name = Column(String(255), nullable=False)
    annual_turnover = Column(Numeric(12, 2), nullable=True)
    net_worth = Column(Numeric(12, 2), nullable=True)
    team_size = Column(Integer, default=0)
    sectors = Column(ARRAY(String), default=[])
    operating_states = Column(ARRAY(String), default=[])
    certifications = Column(JSONB, default={})
    registrations = Column(JSONB, default={})
    years_in_business = Column(Integer, default=0)
    past_projects = Column(JSONB, default=[])
    bid_success_rate = Column(Float, default=0.5)
    liquid_assets = Column(Numeric(12, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="company_profiles")
    tender_scores = relationship("TenderScore", back_populates="company_profile")

# ==================== USAGE LOGS ====================
class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    month = Column(Date, nullable=False)
    tenders_analyzed = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)
    storage_used_mb = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization", back_populates="usage_logs")

# ==================== API LOGS ====================
class ApiLog(Base):
    __tablename__ = "api_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_time_ms = Column(Float, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== TENDER SOURCES (MONITORING) ====================
class SourceType(str, py_enum.Enum):
    """Pluggable monitoring connectors. RSS/HTTP_JSON are live-capable;
    SAMPLE seeds synthetic tenders for demos and local development."""
    RSS = "rss"
    HTTP_JSON = "http_json"
    SAMPLE = "sample"


class TenderSource(Base):
    """An org-configured government portal / feed that is polled for new tenders."""
    __tablename__ = "tender_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), default=SourceType.SAMPLE)
    url = Column(String(1024), nullable=True)
    config = Column(JSONB, default={})           # connector-specific (auth headers, json paths)
    keywords = Column(ARRAY(String), default=[])  # title/desc must match at least one (if set)
    sectors = Column(ARRAY(String), default=[])
    states = Column(ARRAY(String), default=[])
    min_value = Column(Numeric(15, 2), nullable=True)
    max_value = Column(Numeric(15, 2), nullable=True)
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="tender_sources")
    discovered = relationship("DiscoveredTender", back_populates="source")


# ==================== DISCOVERED TENDERS ====================
class DiscoveredStatus(str, py_enum.Enum):
    NEW = "new"
    DISMISSED = "dismissed"
    IMPORTED = "imported"   # promoted into the bid pipeline


class DiscoveredTender(Base):
    """A tender opportunity found by monitoring, scored against the company profile."""
    __tablename__ = "discovered_tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("tender_sources.id"), nullable=False)
    external_id = Column(String(512), nullable=False)  # dedup key within a source
    title = Column(String(1024), nullable=False)
    description = Column(Text, nullable=True)
    tender_value = Column(Numeric(15, 2), nullable=True)
    bid_deadline = Column(DateTime, nullable=True)
    sector = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    url = Column(String(1024), nullable=True)
    match_score = Column(Float, default=0.0)        # 0-1 quick fit vs company profile
    match_reasons = Column(JSONB, default=[])
    status = Column(String(50), default=DiscoveredStatus.NEW)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="discovered_tenders")
    source = relationship("TenderSource", back_populates="discovered")
    bids = relationship("Bid", back_populates="discovered_tender")


# ==================== BIDS (WORKFLOW) ====================
class BidStage(str, py_enum.Enum):
    """Procurement pipeline. Terminal stages: WON, LOST, DROPPED."""
    IDENTIFIED = "identified"
    QUALIFYING = "qualifying"
    GO_NO_GO = "go_no_go"
    PREPARING = "preparing"
    SUBMITTED = "submitted"
    WON = "won"
    LOST = "lost"
    DROPPED = "dropped"


TERMINAL_BID_STAGES = {BidStage.WON, BidStage.LOST, BidStage.DROPPED}


class Bid(Base):
    """A tracked pursuit moving through the procurement pipeline. Originates from
    an uploaded Tender or a DiscoveredTender (or is created manually)."""
    __tablename__ = "bids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    tender_id = Column(UUID(as_uuid=True), ForeignKey("tenders.id"), nullable=True)
    discovered_tender_id = Column(UUID(as_uuid=True), ForeignKey("discovered_tenders.id"), nullable=True)
    title = Column(String(1024), nullable=False)
    stage = Column(String(50), default=BidStage.IDENTIFIED)
    assigned_to_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    tender_value = Column(Numeric(15, 2), nullable=True)
    bid_deadline = Column(DateTime, nullable=True)
    win_probability = Column(Float, nullable=True)   # snapshot from scoring at import
    notes = Column(Text, nullable=True)
    # deadline-alert dedup: list of day-thresholds already notified (e.g. [7, 3, 1])
    deadline_alerts_sent = Column(JSONB, default=[])
    decided_at = Column(DateTime, nullable=True)     # set when entering a terminal stage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="bids")
    tender = relationship("Tender")
    discovered_tender = relationship("DiscoveredTender", back_populates="bids")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    events = relationship("BidEvent", back_populates="bid", order_by="BidEvent.created_at")


class BidEvent(Base):
    """Immutable audit log of stage transitions, assignments, and notes on a bid."""
    __tablename__ = "bid_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bid_id = Column(UUID(as_uuid=True), ForeignKey("bids.id"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    event_type = Column(String(50), nullable=False)  # stage_change | assigned | note | created
    from_value = Column(String(255), nullable=True)
    to_value = Column(String(255), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    bid = relationship("Bid", back_populates="events")
    actor = relationship("User")


# ==================== NOTIFICATIONS / ALERTS ====================
class NotificationType(str, py_enum.Enum):
    NEW_HIGH_MATCH = "new_high_match"
    DEADLINE_APPROACHING = "deadline_approaching"
    BID_ASSIGNED = "bid_assigned"
    STAGE_CHANGED = "stage_changed"


class Notification(Base):
    """In-app (and optionally emailed) alert. user_id null => visible org-wide."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    type = Column(String(50), nullable=False)
    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=True)
    link = Column(String(1024), nullable=True)
    bid_id = Column(UUID(as_uuid=True), ForeignKey("bids.id"), nullable=True)
    discovered_tender_id = Column(UUID(as_uuid=True), ForeignKey("discovered_tenders.id"), nullable=True)
    dedup_key = Column(String(512), nullable=True)  # prevents duplicate alerts
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="notifications")
    user = relationship("User")

