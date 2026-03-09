import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from db.models import Application
from typing import Optional, List


class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_application(
        self,
        customer_id,
        package_id,
        payment_type: str,
        delivery: str,
        team: Optional[str] = None,
        ttl_minutes: int = 30,
    ) -> dict:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        apply_url = f"{base_url}/apply?token={token}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        application = Application(
            customer_id=customer_id,
            package_id=package_id,
            team=team,
            payment_type=payment_type,
            delivery=delivery,
            status="pending",
            apply_token=token_hash,
            apply_url=apply_url,
            token_expires_at=expires_at,
        )
        self.db.add(application)
        self.db.flush()

        return {
            "application_id": str(application.id),
            "apply_url": apply_url,
            "token": token,
            "expires_at": expires_at.isoformat(),
        }

    def get_by_id(self, application_id) -> Optional[Application]:
        return self.db.query(Application).filter(Application.id == application_id).first()

    def update_status(self, application_id, status: str) -> Optional[Application]:
        app = self.get_by_id(application_id)
        if app:
            app.status = status
            self.db.flush()
        return app

    def verify_token(self, token: str) -> Optional[Application]:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        app = self.db.query(Application).filter(Application.apply_token == token_hash).first()
        if not app:
            return None
        if app.token_expires_at and app.token_expires_at < datetime.now(timezone.utc):
            app.status = "expired"
            self.db.flush()
            return None
        return app

    def list_all(self, limit: int = 50, offset: int = 0) -> List[Application]:
        return (
            self.db.query(Application)
            .order_by(Application.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
