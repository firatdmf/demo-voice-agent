import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from db.models import SMSLog

logger = logging.getLogger(__name__)

TEMPLATES = {
    "apply_link": "Basvurunuzu tamamlamak icin linke tiklayin: {apply_url} (30 dk icinde gecerlidir)",
    "menu_fallback": "Devam icin yanitlayin: 1) Taraftar Paketi 2) Sporun Yildizi 3) Internet Paketleri",
}


class SMSService:
    def __init__(self, db: Session):
        self.db = db

    def send_sms(
        self,
        application_id,
        to_phone: str,
        template: str,
        params: Optional[dict] = None,
    ) -> dict:
        params = params or {}
        template_text = TEMPLATES.get(template, template)
        message_body = template_text.format(**params)

        # Demo mode: just log, don't actually send
        logger.info(f"[SMS DEMO] To: {to_phone} | Message: {message_body}")

        sms_log = SMSLog(
            application_id=application_id,
            to_phone=to_phone,
            template=template,
            message_body=message_body,
            status="sent",
            sent_at=datetime.now(timezone.utc),
        )
        self.db.add(sms_log)
        self.db.flush()

        return {
            "sms_id": str(sms_log.id),
            "status": "sent",
            "message": message_body,
        }
