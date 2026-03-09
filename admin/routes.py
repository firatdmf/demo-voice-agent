"""Admin panel routes."""
import os
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from db.database import get_db
from db.models import Package, PackagePricing, Application, CallSession, Customer, SMSLog

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total_calls = db.query(func.count(CallSession.id)).scalar() or 0
    active_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "active").scalar() or 0
    total_applications = db.query(func.count(Application.id)).scalar() or 0
    completed_applications = db.query(func.count(Application.id)).filter(Application.status == "completed").scalar() or 0
    pending_applications = db.query(func.count(Application.id)).filter(Application.status == "pending").scalar() or 0
    link_sent = db.query(func.count(Application.id)).filter(Application.status == "link_sent").scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_packages = db.query(func.count(Package.id)).filter(Package.is_active == True).scalar() or 0

    completion_rate = round((completed_applications / total_applications * 100), 1) if total_applications > 0 else 0

    recent_calls = (
        db.query(CallSession)
        .order_by(CallSession.started_at.desc())
        .limit(5)
        .all()
    )
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
        "total_customers": total_customers,
        "total_packages": total_packages,
        "completion_rate": completion_rate,
        "recent_calls": recent_calls,
        "recent_apps": recent_apps,
    })


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


@router.post("/packages/{package_id}/toggle")
async def toggle_package(package_id: str, db: Session = Depends(get_db)):
    pkg = db.query(Package).filter(Package.id == package_id).first()
    if not pkg:
        raise HTTPException(404, "Paket bulunamadi")
    pkg.is_active = not pkg.is_active
    db.commit()
    return RedirectResponse("/admin/packages", status_code=303)


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
        raise HTTPException(404, "Basvuru bulunamadi")
    return templates.TemplateResponse("application_detail.html", {
        "request": request,
        "app": application,
    })


@router.get("/calls", response_class=HTMLResponse)
async def calls_list(request: Request, db: Session = Depends(get_db)):
    calls = (
        db.query(CallSession)
        .order_by(CallSession.started_at.desc())
        .limit(100)
        .all()
    )
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
        raise HTTPException(404, "Cagri bulunamadi")
    return templates.TemplateResponse("call_detail.html", {
        "request": request,
        "call": call,
    })
