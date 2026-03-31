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


def _check_auth(request: Request):
    """Check authentication, return RedirectResponse if not authenticated."""
    from auth import verify_session
    if not verify_session(request):
        return RedirectResponse("/login", status_code=303)
    return None


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
    apps = customer.applications or []
    calls = customer.call_sessions or []

    teams = [a.team for a in apps if a.team]
    packages = [a.package.name for a in apps if a.package]
    statuses = [a.status for a in apps]
    payment_types = [a.payment_type for a in apps]
    call_summaries = [c.conversation_summary for c in calls if c.conversation_summary]

    prompt = f"""Sen bir Digiturk CRM uzmanisin. Asagidaki musteri bilgilerini analiz et ve Turkce olarak detayli bir musteri profili olustur.

MUSTERI BILGILERI:
- Ad Soyad: {customer.name} {customer.surname}
- Telefon: {customer.phone}
- Sehir: {customer.city or 'Bilinmiyor'}
- Ilce: {customer.district or 'Bilinmiyor'}
- Dogum Tarihi: {customer.birth_date or 'Bilinmiyor'}
- Kayit Tarihi: {customer.created_at}

BASVURU GECMISI ({len(apps)} basvuru):
- Tercih edilen takimlar: {', '.join(teams) if teams else 'Belirtilmemis'}
- Ilgilendigi paketler: {', '.join(packages) if packages else 'Yok'}
- Basvuru durumlari: {', '.join(statuses) if statuses else 'Yok'}
- Odeme tercihleri: {', '.join(payment_types) if payment_types else 'Yok'}

CAGRI GECMISI ({len(calls)} cagri):
- Gorusme ozetleri: {' | '.join(call_summaries) if call_summaries else 'Ozet yok'}

Lutfen su basliklar altinda analiz yap:

MUSTERI PROFILI
Musterinin genel profili hakkinda kisa bir degerlendirme.

SATIN ALMA EGILIMI
Bu musterinin satin alma olasiligi nedir? (Yuksek/Orta/Dusuk) ve neden?

ILGI ALANLARI
Musterinin spor/eglence tercihleri ve takim tutkusu hakkinda degerlendirme.

ONERILER
Bu musteriye nasil yaklasilmali? Hangi paketler onerilmeli?

DIKKAT EDILMESI GEREKENLER
Musteri ile iletisimde dikkat edilmesi gereken noktalar.
"""

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen bir Digiturk CRM musteri analiz uzmanisin. Turkce yanit ver."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI analiz hatasi: {e}")
        return f"AI analizi olusturulurken bir hata olustu: {str(e)}\n\nLutfen OPENAI_API_KEY ortam degiskeninin dogru ayarlandigindan emin olun."


# ─── DASHBOARD ──────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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

    # === NEW METRICS ===
    from sqlalchemy import func as sqlfunc

    # Average duration
    avg_duration_val = db.query(func.avg(CallSession.duration_seconds)).filter(
        CallSession.duration_seconds > 0
    ).scalar()
    avg_duration = round(float(avg_duration_val), 1) if avg_duration_val else 0

    # Success rate
    completed_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "completed").scalar() or 0
    success_rate = round((completed_calls / total_calls * 100), 1) if total_calls > 0 else 0

    # Today stats
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_calls = db.query(func.count(CallSession.id)).filter(CallSession.started_at >= today_start).scalar() or 0
    today_applications = db.query(func.count(Application.id)).filter(Application.created_at >= today_start).scalar() or 0

    # Conversion funnel
    funnel_rows = db.query(CallSession.dropped_at_state, func.count(CallSession.id)).filter(
        CallSession.dropped_at_state.isnot(None)
    ).group_by(CallSession.dropped_at_state).all()
    conversion_funnel = {s: c for s, c in funnel_rows}

    # Hourly distribution today
    today_calls_rows = db.query(CallSession.started_at).filter(CallSession.started_at >= today_start).all()
    hourly_distribution = {h: 0 for h in range(24)}
    for row in today_calls_rows:
        if row.started_at:
            hourly_distribution[row.started_at.hour] += 1

    # Sentiment
    sentiment_rows = db.query(CallSession.customer_sentiment, func.count(CallSession.id)).filter(
        CallSession.customer_sentiment.isnot(None)
    ).group_by(CallSession.customer_sentiment).all()
    sentiment_distribution = {s: c for s, c in sentiment_rows}

    # Recontact list
    recontact_list = db.query(CallSession).options(joinedload(CallSession.customer)).filter(
        CallSession.recontact_priority.in_(["high", "medium"]),
        CallSession.recontact_score > 0,
    ).order_by(CallSession.recontact_score.desc()).limit(10).all()

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
        "avg_duration": avg_duration,
        "success_rate": success_rate,
        "today_calls": today_calls,
        "today_applications": today_applications,
        "conversion_funnel": conversion_funnel,
        "hourly_distribution": hourly_distribution,
        "sentiment_distribution": sentiment_distribution,
        "recontact_list": recontact_list,
    })


# ─── MUSTERILER ────────────────────────────────────────────

@router.get("/customers", response_class=HTMLResponse)
async def customers_list(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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
async def analyze_customer(customer_id: str, request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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


# ─── ANALITIK ──────────────────────────────────────────────

@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, period: str = "7d", db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    now = datetime.now(timezone.utc)

    # Period filter
    period_map = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
    }
    delta = period_map.get(period, timedelta(days=7))
    period_start = now - delta
    period_label = {"24h": "Son 24 Saat", "7d": "Son 7 Gün", "30d": "Son 30 Gün", "90d": "Son 90 Gün"}.get(period, "Son 7 Gün")

    # Base filtered queries
    period_calls = db.query(CallSession).filter(CallSession.started_at >= period_start)
    period_apps = db.query(Application).filter(Application.created_at >= period_start)

    # KPIs
    total_calls = period_calls.count()
    successful_calls = period_calls.filter(CallSession.status == "completed").count()
    failed_calls = period_calls.filter(CallSession.status.in_(["failed", "abused"])).count()
    total_apps = period_apps.count()
    conversion_rate = round((total_apps / total_calls * 100), 1) if total_calls > 0 else 0

    avg_duration_val = db.query(func.avg(CallSession.duration_seconds)).filter(
        CallSession.started_at >= period_start, CallSession.duration_seconds > 0
    ).scalar()
    avg_duration = round(float(avg_duration_val), 1) if avg_duration_val else 0

    # Team distribution (period filtered)
    team_rows = (
        db.query(Application.team, func.count(Application.id))
        .filter(Application.created_at >= period_start, Application.team.isnot(None), Application.team != "")
        .group_by(Application.team)
        .order_by(func.count(Application.id).desc())
        .all()
    )
    team_dist = OrderedDict((t, c) for t, c in team_rows)
    team_total = sum(team_dist.values())
    top_team = max(team_dist, key=team_dist.get) if team_dist else None
    top_team_count = team_dist.get(top_team, 0) if top_team else 0

    # Package demand (period filtered)
    pkg_rows = (
        db.query(Package.name, func.count(Application.id))
        .join(Application, Application.package_id == Package.id)
        .filter(Application.created_at >= period_start)
        .group_by(Package.name)
        .order_by(func.count(Application.id).desc())
        .all()
    )
    package_demand = OrderedDict((name, cnt) for name, cnt in pkg_rows)
    top_package_name = pkg_rows[0][0] if pkg_rows else None
    top_package_count = pkg_rows[0][1] if pkg_rows else 0

    # Payment distribution (period filtered)
    pay_rows = (
        db.query(Application.payment_type, func.count(Application.id))
        .filter(Application.created_at >= period_start)
        .group_by(Application.payment_type)
        .all()
    )
    payment_distribution = {pt: cnt for pt, cnt in pay_rows}

    # Delivery distribution (period filtered)
    del_rows = (
        db.query(Application.delivery, func.count(Application.id))
        .filter(Application.created_at >= period_start)
        .group_by(Application.delivery)
        .all()
    )
    delivery_distribution = {d: cnt for d, cnt in del_rows}

    # City distribution
    city_rows = (
        db.query(Customer.city, func.count(Customer.id))
        .filter(Customer.city.isnot(None), Customer.city != "", Customer.created_at >= period_start)
        .group_by(Customer.city)
        .order_by(func.count(Customer.id).desc())
        .limit(10)
        .all()
    )
    city_distribution = OrderedDict((city, cnt) for city, cnt in city_rows)

    # Daily trend (adjusted for period)
    if period == "24h":
        # Hourly trend for 24h
        hourly_calls = {}
        hourly_apps = {}
        call_rows = db.query(CallSession.started_at).filter(CallSession.started_at >= period_start).all()
        app_rows_raw = db.query(Application.created_at).filter(Application.created_at >= period_start).all()
        for r in call_rows:
            if r.started_at:
                h = r.started_at.strftime("%H:00")
                hourly_calls[h] = hourly_calls.get(h, 0) + 1
        for r in app_rows_raw:
            if r.created_at:
                h = r.created_at.strftime("%H:00")
                hourly_apps[h] = hourly_apps.get(h, 0) + 1
        all_hours = [f"{h:02d}:00" for h in range(24)]
        daily_trend = {
            "dates": all_hours,
            "calls": [hourly_calls.get(h, 0) for h in all_hours],
            "applications": [hourly_apps.get(h, 0) for h in all_hours],
        }
    else:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(period, 7)
        daily_trend = _daily_trend(db, days)

    # Sentiment distribution (period filtered)
    sentiment_rows = (
        db.query(CallSession.customer_sentiment, func.count(CallSession.id))
        .filter(CallSession.started_at >= period_start, CallSession.customer_sentiment.isnot(None))
        .group_by(CallSession.customer_sentiment)
        .all()
    )
    sentiment_distribution = OrderedDict((s, c) for s, c in sentiment_rows)

    # Dropped at state / funnel (period filtered)
    funnel_rows = (
        db.query(CallSession.dropped_at_state, func.count(CallSession.id))
        .filter(CallSession.started_at >= period_start, CallSession.dropped_at_state.isnot(None))
        .group_by(CallSession.dropped_at_state)
        .all()
    )
    dropped_funnel = OrderedDict((s, c) for s, c in funnel_rows)

    # Customer segments
    segment_rows = (
        db.query(Customer.customer_segment, func.count(Customer.id))
        .filter(Customer.customer_segment.isnot(None))
        .group_by(Customer.customer_segment)
        .all()
    )
    customer_segments = {s: c for s, c in segment_rows}

    # Recontact stats
    recontact_high = db.query(func.count(CallSession.id)).filter(
        CallSession.started_at >= period_start, CallSession.recontact_priority == "high"
    ).scalar() or 0
    recontact_medium = db.query(func.count(CallSession.id)).filter(
        CallSession.started_at >= period_start, CallSession.recontact_priority == "medium"
    ).scalar() or 0
    avg_recontact = db.query(func.avg(CallSession.recontact_score)).filter(
        CallSession.started_at >= period_start, CallSession.recontact_score > 0
    ).scalar()
    avg_recontact_score = round(float(avg_recontact), 1) if avg_recontact else 0

    return templates.TemplateResponse("analytics.html", {
        "request": request,
        "period": period,
        "period_label": period_label,
        "total_calls": total_calls,
        "successful_calls": successful_calls,
        "failed_calls": failed_calls,
        "total_apps": total_apps,
        "conversion_rate": conversion_rate,
        "avg_duration": avg_duration,
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
        "sentiment_distribution": sentiment_distribution,
        "dropped_funnel": dropped_funnel,
        "customer_segments": customer_segments,
        "recontact_high": recontact_high,
        "recontact_medium": recontact_medium,
        "avg_recontact_score": avg_recontact_score,
    })


# ─── PAKETLER ───────────────────────────────────────────────

@router.get("/packages", response_class=HTMLResponse)
async def packages_list(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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
    features: str = Form(""),
):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    existing = db.query(Package).filter(Package.package_id == package_id).first()
    if existing:
        raise HTTPException(400, "Bu Paket ID zaten mevcut")

    teams_list = [t.strip() for t in teams_supported.split(",") if t.strip()] if teams_supported else []
    features_list = [f.strip() for f in features.split(",") if f.strip()] if features else []

    pkg = Package(
        package_id=package_id,
        name=name,
        category=category,
        delivery=delivery,
        platform=platform or None,
        team_required=bool(team_required),
        teams_supported=teams_list,
        features=features_list,
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
                        amount_monthly=amount,
                        payment_type=ptype,
                        currency="TRY",
                    )
                    db.add(pricing)
            except Exception:
                pass

    db.commit()
    return RedirectResponse("/admin/packages", status_code=303)


@router.post("/packages/{package_id}/toggle")
async def toggle_package(package_id: str, request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadı")
    pkg.is_active = not pkg.is_active
    db.commit()
    return RedirectResponse("/admin/packages", status_code=303)


# ─── HTMX PACKAGE ENDPOINTS ─────────────────────────────────

@router.post("/packages/add-htmx", response_class=HTMLResponse)
async def add_package_htmx(
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
    features: str = Form(""),
):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    existing = db.query(Package).filter(Package.package_id == package_id).first()
    if existing:
        return HTMLResponse("<div class='alert alert-danger'>Bu Paket ID zaten mevcut</div>", status_code=400)

    teams_list = [t.strip() for t in teams_supported.split(",") if t.strip()] if teams_supported else []
    features_list = [f.strip() for f in features.split(",") if f.strip()] if features else []

    pkg = Package(
        package_id=package_id,
        name=name,
        category=category,
        delivery=delivery,
        platform=platform or None,
        team_required=bool(team_required),
        teams_supported=teams_list,
        features=features_list,
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
                        amount_monthly=amount,
                        payment_type=ptype,
                        currency="TRY",
                    )
                    db.add(pricing)
            except Exception:
                pass

    db.commit()

    # Reload with pricing
    pkg = db.query(Package).options(joinedload(Package.pricing)).filter(Package.id == pkg.id).first()

    return templates.TemplateResponse("partials/package_card.html", {
        "request": request,
        "pkg": pkg,
    })


@router.post("/packages/{package_id}/toggle-htmx", response_class=HTMLResponse)
async def toggle_package_htmx(package_id: str, request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    pkg = db.query(Package).options(joinedload(Package.pricing)).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadı")
    pkg.is_active = not pkg.is_active
    db.commit()

    return templates.TemplateResponse("partials/package_card.html", {
        "request": request,
        "pkg": pkg,
    })


@router.post("/packages/{package_id}/update-htmx", response_class=HTMLResponse)
async def update_package_htmx(
    package_id: str,
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(...),
    category: str = Form(...),
    delivery: str = Form(...),
    platform: str = Form(""),
    team_required: str = Form(""),
    teams_supported: str = Form(""),
    features: str = Form(""),
    price_cc: str = Form(""),
    price_invoiced: str = Form(""),
    price_monthly: str = Form(""),
    **kwargs,
):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    pkg = db.query(Package).options(joinedload(Package.pricing)).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadı")

    pkg.name = name
    pkg.category = category
    pkg.delivery = delivery
    pkg.platform = platform or None
    pkg.team_required = bool(team_required)
    pkg.teams_supported = [t.strip() for t in teams_supported.split(",") if t.strip()] if teams_supported else []
    pkg.features = [f.strip() for f in features.split(",") if f.strip()] if features else []

    # Update pricing - delete old, create new
    for old_price in pkg.pricing:
        db.delete(old_price)
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
                        amount_monthly=amount,
                        payment_type=ptype,
                        currency="TRY",
                    )
                    db.add(pricing)
            except Exception:
                pass

    db.commit()
    pkg = db.query(Package).options(joinedload(Package.pricing)).filter(Package.id == pkg.id).first()

    return templates.TemplateResponse("partials/package_card.html", {
        "request": request,
        "pkg": pkg,
    })


@router.delete("/packages/{package_id}/delete-htmx", response_class=HTMLResponse)
async def delete_package_htmx(package_id: str, request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    pkg = db.query(Package).options(joinedload(Package.pricing)).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadı")

    # Delete pricing first
    for price in pkg.pricing:
        db.delete(price)

    db.delete(pkg)
    db.commit()

    # Return empty string - HTMX will remove the card
    return HTMLResponse("")


# ─── BASVURULAR ─────────────────────────────────────────────

@router.get("/applications", response_class=HTMLResponse)
async def applications_list(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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


# ─── CAGRILAR ───────────────────────────────────────────────

@router.get("/calls", response_class=HTMLResponse)
async def calls_list(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    calls = db.query(CallSession).order_by(CallSession.started_at.desc()).limit(100).all()
    return templates.TemplateResponse("calls.html", {
        "request": request,
        "calls": calls,
    })


@router.get("/calls/{call_id}", response_class=HTMLResponse)
async def call_detail(call_id: str, request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

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


# ─── TEKRAR ARANACAKLAR ────────────────────────────────────

@router.get("/recontact", response_class=HTMLResponse)
async def recontact_list(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    recontact_calls = (
        db.query(CallSession)
        .options(joinedload(CallSession.customer))
        .filter(
            CallSession.recontact_priority.in_(["high", "medium", "low"]),
            CallSession.recontact_score > 0,
        )
        .order_by(CallSession.recontact_score.desc())
        .limit(50)
        .all()
    )

    high_count = sum(1 for c in recontact_calls if c.recontact_priority == "high")
    medium_count = sum(1 for c in recontact_calls if c.recontact_priority == "medium")
    low_count = sum(1 for c in recontact_calls if c.recontact_priority == "low")

    return templates.TemplateResponse("recontact.html", {
        "request": request,
        "recontact_calls": recontact_calls,
        "high_count": high_count,
        "medium_count": medium_count,
        "low_count": low_count,
        "total_count": len(recontact_calls),
    })


# ─── PROFİL ───────────────────────────────────────────────

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect
    from auth import ADMIN_USERNAME
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "username": ADMIN_USERNAME,
    })


@router.post("/profile/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    if new_password != confirm_password:
        return HTMLResponse('<div class="alert alert-danger"><i class="bi bi-x-circle me-2"></i>Yeni şifreler eşleşmiyor</div>')

    from auth import change_password as auth_change_pw
    success, error = auth_change_pw(current_password, new_password)
    if not success:
        return HTMLResponse(f'<div class="alert alert-danger"><i class="bi bi-x-circle me-2"></i>{error}</div>')

    return HTMLResponse('<div class="alert alert-success"><i class="bi bi-check-circle me-2"></i>Şifre başarıyla değiştirildi</div>')


# ─── AYARLAR ──────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    auth_redirect = _check_auth(request)
    if auth_redirect:
        return auth_redirect

    import os
    import sys
    settings = {
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest"),
        "gemini_voice": os.getenv("GEMINI_VOICE", "Kore"),
        "language": os.getenv("GEMINI_LANGUAGE", "tr-TR"),
        "admin_username": os.getenv("ADMIN_USERNAME", "admin"),
        "sms_enabled": os.getenv("SMS_ENABLED", "true"),
        "auto_analysis": os.getenv("AUTO_ANALYSIS", "true"),
        "max_call_duration": os.getenv("MAX_CALL_DURATION", "600"),
        "greeting_enabled": os.getenv("GREETING_ENABLED", "true"),
    }

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "python_version": sys.version.split()[0],
    })
