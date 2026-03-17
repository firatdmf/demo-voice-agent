"""Admin panel routes."""
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections import OrderedDict

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date

from db.database import get_db
from db.models import Package, PackagePricing, Application, CallSession, Customer, SMSLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

_STATUS_TR = {
    "completed": "Tamamlandı",
    "active": "Aktif",
    "pending": "Beklemede",
    "failed": "Başarısız",
    "link_sent": "Link Gönderildi",
    "expired": "Süresi Doldu",
    "abused": "Kötüye Kullanım",
    "sent": "Gönderildi",
}

templates.env.filters["status_tr"] = lambda s: _STATUS_TR.get(s, s)


def _team_distribution(db: Session) -> dict:
    rows = (
        db.query(Application.team, func.count(Application.id))
        .filter(Application.team.isnot(None), Application.team != "")
        .group_by(Application.team)
        .order_by(func.count(Application.id).desc())
        .all()
    )
    return {team: count for team, count in rows}


def _daily_trend(db: Session, days: int = 30) -> dict:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days - 1)

    call_rows = (
        db.query(cast(CallSession.started_at, Date), func.count(CallSession.id))
        .filter(cast(CallSession.started_at, Date) >= start)
        .group_by(cast(CallSession.started_at, Date))
        .all()
    )
    app_rows = (
        db.query(cast(Application.created_at, Date), func.count(Application.id))
        .filter(cast(Application.created_at, Date) >= start)
        .group_by(cast(Application.created_at, Date))
        .all()
    )

    call_map = {str(d): c for d, c in call_rows}
    app_map = {str(d): c for d, c in app_rows}

    dates, calls, apps = [], [], []
    for i in range(days):
        d = start + timedelta(days=i)
        ds = str(d)
        dates.append(d.strftime("%d.%m"))
        calls.append(call_map.get(ds, 0))
        apps.append(app_map.get(ds, 0))

    return {"dates": dates, "calls": calls, "applications": apps}


async def _generate_ai_analysis(customer: Customer, db: Session) -> str:
    """Generate AI analysis for a customer using OpenAI."""
    # Collect customer data
    apps = customer.applications or []
    calls = customer.call_sessions or []

    teams = [a.team for a in apps if a.team]
    packages = [a.package.name for a in apps if a.package]
    statuses = [a.status for a in apps]
    payment_types = [a.payment_type for a in apps]
    call_summaries = [c.conversation_summary for c in calls if c.conversation_summary]

    prompt = f"""Sen bir Digiturk CRM uzmanısın. Aşağıdaki müşteri bilgilerini analiz et ve Türkçe olarak detaylı bir müşteri profili oluştur.

MÜŞTERİ BİLGİLERİ:
- Ad Soyad: {customer.name} {customer.surname}
- Telefon: {customer.phone}
- Şehir: {customer.city or 'Bilinmiyor'}
- İlçe: {customer.district or 'Bilinmiyor'}
- Doğum Tarihi: {customer.birth_date or 'Bilinmiyor'}
- Kayıt Tarihi: {customer.created_at}

BAŞVURU GEÇMİŞİ ({len(apps)} başvuru):
- Tercih edilen takımlar: {', '.join(teams) if teams else 'Belirtilmemiş'}
- İlgilendiği paketler: {', '.join(packages) if packages else 'Yok'}
- Başvuru durumları: {', '.join(statuses) if statuses else 'Yok'}
- Ödeme tercihleri: {', '.join(payment_types) if payment_types else 'Yok'}

ÇAĞRI GEÇMİŞİ ({len(calls)} çağrı):
- Görüşme özetleri: {' | '.join(call_summaries) if call_summaries else 'Özet yok'}

Lütfen şu başlıklar altında analiz yap:

📋 MÜŞTERİ PROFİLİ
Müşterinin genel profili hakkında kısa bir değerlendirme.

🎯 SATIN ALMA EĞİLİMİ
Bu müşterinin satın alma olasılığı nedir? (Yüksek/Orta/Düşük) ve neden?

⚽ İLGİ ALANLARI
Müşterinin spor/eğlence tercihleri ve takım tutkusu hakkında değerlendirme.

💡 ÖNERİLER
Bu müşteriye nasıl yaklaşılmalı? Hangi paketler önerilmeli?

⚠️ DİKKAT EDİLMESİ GEREKENLER
Müşteri ile iletişimde dikkat edilmesi gereken noktalar.
"""

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen bir Digiturk CRM müşteri analiz uzmanısın. Türkçe yanıt ver."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI analiz hatası: {e}")
        return f"⚠️ AI analizi oluşturulurken bir hata oluştu: {str(e)}\n\nLütfen OPENAI_API_KEY ortam değişkeninin doğru ayarlandığından emin olun."


# ─── DASHBOARD ──────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total_calls = db.query(func.count(CallSession.id)).scalar() or 0
    active_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "active").scalar() or 0
    total_applications = db.query(func.count(Application.id)).scalar() or 0
    completed_applications = db.query(func.count(Application.id)).filter(Application.status == "completed").scalar() or 0
    pending_applications = db.query(func.count(Application.id)).filter(Application.status == "pending").scalar() or 0
    link_sent = db.query(func.count(Application.id)).filter(Application.status == "link_sent").scalar() or 0
    expired_applications = db.query(func.count(Application.id)).filter(Application.status == "expired").scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_packages = db.query(func.count(Package.id)).filter(Package.is_active == True).scalar() or 0

    completion_rate = round((completed_applications / total_applications * 100), 1) if total_applications > 0 else 0
    team_dist = _team_distribution(db)

    recent_calls = db.query(CallSession).order_by(CallSession.started_at.desc()).limit(5).all()
    recent_apps = (
        db.query(Application)
        .options(joinedload(Application.customer), joinedload(Application.package))
        .order_by(Application.created_at.desc())
        .limit(5)
        .all()
    )

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_calls": total_calls,
        "active_calls": active_calls,
        "total_applications": total_applications,
        "completed_applications": completed_applications,
        "pending_applications": pending_applications,
        "link_sent": link_sent,
        "expired_applications": expired_applications,
        "total_customers": total_customers,
        "total_packages": total_packages,
        "completion_rate": completion_rate,
        "team_distribution": team_dist,
        "recent_calls": recent_calls,
        "recent_apps": recent_apps,
    })


# ─── MÜŞTERİLER ────────────────────────────────────────────

@router.get("/customers", response_class=HTMLResponse)
async def customers_list(request: Request, db: Session = Depends(get_db)):
    customers = (
        db.query(Customer)
        .options(joinedload(Customer.applications))
        .order_by(Customer.created_at.desc())
        .limit(200)
        .all()
    )
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    customers_with_apps = db.query(func.count(func.distinct(Application.customer_id))).scalar() or 0
    unique_cities = (
        db.query(func.count(func.distinct(Customer.city)))
        .filter(Customer.city.isnot(None), Customer.city != "")
        .scalar() or 0
    )
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    new_this_month = db.query(func.count(Customer.id)).filter(Customer.created_at >= month_start).scalar() or 0

    return templates.TemplateResponse("customers.html", {
        "request": request,
        "customers": customers,
        "total_customers": total_customers,
        "customers_with_apps": customers_with_apps,
        "unique_cities": unique_cities,
        "new_this_month": new_this_month,
    })


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
async def customer_detail(customer_id: str, request: Request, db: Session = Depends(get_db)):
    customer = (
        db.query(Customer)
        .options(
            joinedload(Customer.applications).joinedload(Application.package),
            joinedload(Customer.call_sessions),
        )
        .filter(Customer.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(404, "Müşteri bulunamadı")
    return templates.TemplateResponse("customer_detail.html", {
        "request": request,
        "customer": customer,
    })


@router.post("/customers/{customer_id}/analyze")
async def analyze_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = (
        db.query(Customer)
        .options(
            joinedload(Customer.applications).joinedload(Application.package),
            joinedload(Customer.call_sessions),
        )
        .filter(Customer.id == customer_id)
        .first()
    )
    if not customer:
        raise HTTPException(404, "Müşteri bulunamadı")

    analysis = await _generate_ai_analysis(customer, db)
    customer.ai_notes = analysis
    customer.ai_analysis_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(f"/admin/customers/{customer_id}", status_code=303)


# ─── ANALİTİK ──────────────────────────────────────────────

@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, db: Session = Depends(get_db)):
    total_calls = db.query(func.count(CallSession.id)).scalar() or 0
    successful_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "completed").scalar() or 0
    failed_calls = db.query(func.count(CallSession.id)).filter(CallSession.status.in_(["failed", "abused"])).scalar() or 0
    total_apps = db.query(func.count(Application.id)).scalar() or 0
    conversion_rate = round((total_apps / total_calls * 100), 1) if total_calls > 0 else 0

    team_dist = _team_distribution(db)
    team_total = sum(team_dist.values())
    top_team = max(team_dist, key=team_dist.get) if team_dist else None
    top_team_count = team_dist.get(top_team, 0) if top_team else 0

    pkg_rows = (
        db.query(Package.name, func.count(Application.id))
        .join(Application, Application.package_id == Package.id)
        .group_by(Package.name)
        .order_by(func.count(Application.id).desc())
        .all()
    )
    package_demand = OrderedDict((name, cnt) for name, cnt in pkg_rows)
    top_package_name = pkg_rows[0][0] if pkg_rows else None
    top_package_count = pkg_rows[0][1] if pkg_rows else 0

    pay_rows = db.query(Application.payment_type, func.count(Application.id)).group_by(Application.payment_type).all()
    payment_distribution = {pt: cnt for pt, cnt in pay_rows}

    del_rows = db.query(Application.delivery, func.count(Application.id)).group_by(Application.delivery).all()
    delivery_distribution = {d: cnt for d, cnt in del_rows}

    city_rows = (
        db.query(Customer.city, func.count(Customer.id))
        .filter(Customer.city.isnot(None), Customer.city != "")
        .group_by(Customer.city)
        .order_by(func.count(Customer.id).desc())
        .limit(10)
        .all()
    )
    city_distribution = OrderedDict((city, cnt) for city, cnt in city_rows)
    daily_trend = _daily_trend(db)

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "conversion_rate": conversion_rate,
        "team_distribution": team_dist,
        "team_total": team_total,
        "top_team": top_team,
        "top_team_count": top_team_count,
        "package_demand": package_demand,
        "top_package_name": top_package_name,
        "top_package_count": top_package_count,
        "payment_distribution": payment_distribution,
        "delivery_distribution": delivery_distribution,
        "city_distribution": city_distribution,
        "daily_trend": daily_trend,
    })


# ─── PAKETLER ───────────────────────────────────────────────

@router.get("/packages", response_class=HTMLResponse)
async def packages_list(request: Request, db: Session = Depends(get_db)):
    packages = (
        db.query(Package)
        .options(joinedload(Package.pricing))
        .order_by(Package.category, Package.name)
        .all()
    )
    return templates.TemplateResponse("packages.html", {
        "request": request,
        "packages": packages,
    })


@router.post("/packages/add")
async def add_package(
    request: Request,
    db: Session = Depends(get_db),
    package_id: str = Form(...),
    name: str = Form(...),
    category: str = Form(...),
    delivery: str = Form(...),
    platform: str = Form(""),
    team_required: str = Form(""),
    teams_supported: str = Form(""),
    price_cc: str = Form(""),
    price_invoiced: str = Form(""),
    price_monthly: str = Form(""),
):
    existing = db.query(Package).filter(Package.package_id == package_id).first()
    if existing:
        raise HTTPException(400, "Bu Paket ID zaten mevcut")

    teams_list = [t.strip() for t in teams_supported.split(",") if t.strip()] if teams_supported else []

    pkg = Package(
        package_id=package_id,
        name=name,
        category=category,
        delivery=delivery,
        platform=platform or None,
        team_required=bool(team_required),
        teams_supported=teams_list,
        is_active=True,
    )
    db.add(pkg)
    db.flush()

    for ptype, amount_str in [
        ("credit_card_installment_12", price_cc),
        ("invoiced", price_invoiced),
        ("monthly", price_monthly),
    ]:
        if amount_str and amount_str.strip():
            try:
                amount = Decimal(amount_str.strip())
                if amount > 0:
                    pricing = PackagePricing(
                        package_id=pkg.id,
                        payment_type=ptype,
                        amount_monthly=amount,
                        currency="TRY",
                    )
                    db.add(pricing)
            except Exception:
                pass

    db.commit()
    return RedirectResponse("/admin/packages", status_code=303)


@router.post("/packages/{package_id}/toggle")
async def toggle_package(package_id: str, db: Session = Depends(get_db)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadı")
    pkg.is_active = not pkg.is_active
    db.commit()
    return RedirectResponse("/admin/packages", status_code=303)


# ─── BAŞVURULAR ─────────────────────────────────────────────

@router.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request, db: Session = Depends(get_db)):
    applications = (
        db.query(Application)
        .options(joinedload(Application.customer), joinedload(Application.package))
        .order_by(Application.created_at.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse("applications.html", {
        "request": request,
        "applications": applications,
    })


@router.get("/applications/{app_id}", response_class=HTMLResponse)
async def application_detail(app_id: str, request: Request, db: Session = Depends(get_db)):
    application = (
        db.query(Application)
        .options(
            joinedload(Application.customer),
            joinedload(Application.package),
            joinedload(Application.sms_logs),
        )
        .filter(Application.id == app_id)
        .first()
    )
    if not application:
        raise HTTPException(404, "Başvuru bulunamadı")
    return templates.TemplateResponse("application_detail.html", {
        "request": request,
        "app": application,
    })


# ─── ÇAĞRILAR ───────────────────────────────────────────────

@router.get("/calls", response_class=HTMLResponse)
async def calls_list(request: Request, db: Session = Depends(get_db)):
    calls = db.query(CallSession).order_by(CallSession.started_at.desc()).limit(100).all()
    return templates.TemplateResponse("calls.html", {
        "request": request,
        "calls": calls,
    })


@router.get("/calls/{call_id}", response_class=HTMLResponse)
async def call_detail(call_id: str, request: Request, db: Session = Depends(get_db)):
    call = (
        db.query(CallSession)
        .options(joinedload(CallSession.customer), joinedload(CallSession.application))
        .filter(CallSession.id == call_id)
        .first()
    )
    if not call:
        raise HTTPException(404, "Çağrı bulunamadı")
    return templates.TemplateResponse("call_detail.html", {
        "request": request,
        "call": call,
    })
