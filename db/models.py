import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, Integer,
    Numeric, ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Package(Base):
    __tablename__ = "packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)  # kampanyali_paketler / kutulu_paketler / internet_paketleri
    delivery = Column(String(20), nullable=False)  # kutusuz / kutulu
    platform = Column(String(100))
    team_required = Column(Boolean, default=False)
    teams_supported = Column(JSON, default=list)
    notes = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    pricing = relationship("PackagePricing", back_populates="package", cascade="all, delete-orphan")


class PackagePricing(Base):
    __tablename__ = "package_pricing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id", ondelete="CASCADE"), nullable=False)
    payment_type = Column(String(50), nullable=False)  # credit_card_installment_12 / invoiced / monthly
    amount_monthly = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="TRY")

    package = relationship("Package", back_populates="pricing")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    surname = Column(String(100), nullable=False)
    tckn = Column(String(256))  # encrypted
    birth_date = Column(Date)
    phone = Column(String(20), nullable=False)
    city = Column(String(100))
    district = Column(String(100))
    neighborhood = Column(String(100))
    street = Column(String(200))
    building_no = Column(String(20))
    apartment_no = Column(String(20))
    address_freeform = Column(Text)
    ai_notes = Column(Text)  # AI tarafından oluşturulan müşteri analizi
    ai_analysis_at = Column(DateTime(timezone=True))  # Son analiz tarihi
    created_at = Column(DateTime(timezone=True), default=utcnow)

    applications = relationship("Application", back_populates="customer")
    call_sessions = relationship("CallSession", back_populates="customer")


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    package_id = Column(UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False)
    team = Column(String(100))
    payment_type = Column(String(50), nullable=False)
    delivery = Column(String(20), nullable=False)
    status = Column(String(20), default="pending")  # pending / link_sent / completed / expired
    apply_token = Column(String(256))
    apply_url = Column(String(500))
    token_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer = relationship("Customer", back_populates="applications")
    package = relationship("Package")
    call_sessions = relationship("CallSession", back_populates="application")
    sms_logs = relationship("SMSLog", back_populates="application")


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twilio_call_sid = Column(String(100), unique=True, index=True)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True)
    caller_phone = Column(String(20))
    state_history = Column(JSON, default=list)
    conversation_summary = Column(Text)
    flags = Column(JSON, default=list)  # low_confidence, offtopic, abuse
    started_at = Column(DateTime(timezone=True), default=utcnow)
    ended_at = Column(DateTime(timezone=True))
    status = Column(String(20), default="active")  # active / completed / failed / abused

    customer = relationship("Customer", back_populates="call_sessions")
    application = relationship("Application", back_populates="call_sessions")


class SMSLog(Base):
    __tablename__ = "sms_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    to_phone = Column(String(20), nullable=False)
    template = Column(String(100))
    message_body = Column(Text)
    status = Column(String(20), default="sent")  # sent / failed
    sent_at = Column(DateTime(timezone=True), default=utcnow)

    application = relationship("Application", back_populates="sms_logs")
