"""FastAPI main application - Twilio webhooks, WebSocket endpoint, admin panel."""
import os
import logging
from contextlib import asynccontextmanager

from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from twilio.twiml.voice_response import VoiceResponse, Connect

from db.database import engine, Base, get_db, SessionLocal
from db.models import Package
from admin.routes import router as admin_router
from websocket_handler import TwilioOpenAIBridge
from browser_bridge import BrowserGeminiBridge
from services.application_service import ApplicationService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Startup: create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")

        # Check if packages are seeded
        db = SessionLocal()
        pkg_count = db.query(Package).count()
        db.close()
        if pkg_count == 0:
            logger.warning("No packages found. Run 'python db/seed.py' to seed the database.")
        else:
            logger.info(f"{pkg_count} packages found in database")
    except Exception as e:
        logger.error(f"Database startup error (non-fatal): {e}")

    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Digiturk Bayi AI Voice Agent",
    description="AI-powered voice sales call center for Digiturk dealer",
    version="1.0.0",
    lifespan=lifespan,
)

# Include admin routes
app.include_router(admin_router)


# ── Live Analysis API ──

class LiveAnalysisRequest(BaseModel):
    messages: list
    state: Optional[str] = None
    customer_name: Optional[str] = None
    interest: Optional[str] = None
    package_id: Optional[str] = None
    is_final: bool = False


@app.post("/api/live-analysis")
async def live_analysis(req: LiveAnalysisRequest):
    """Real-time customer analysis during a call using OpenAI."""
    import json as _json

    conversation_text = "\n".join(
        f"{'Musteri' if m.get('role') == 'user' else 'Temsilci'}: {m.get('text', '')}"
        for m in req.messages
    )

    analysis_prompt = f"""Sen bir Digiturk satis analiz uzmanisın. Asagidaki canli gorusmeyi analiz et ve JSON formatinda yanit ver.

GORUSME METNI:
{conversation_text}

EK BILGILER:
- Gorusme durumu: {req.state or 'Bilinmiyor'}
- Musteri adi: {req.customer_name or 'Henuz bilinmiyor'}
- Ilgi alani: {req.interest or 'Henuz belirlenmedi'}
- Secilen paket: {req.package_id or 'Henuz secilmedi'}
- Gorusme {'sona erdi' if req.is_final else 'devam ediyor'}

Asagidaki JSON formatinda SADECE JSON olarak yanit ver, baska bir sey yazma:
{{
    "purchase_intent": <0-100 arasi sayi, musterinin satin alma olasiligi>,
    "intent_reason": "<tek cumle: neden bu skor>",
    "mood": "<positive|neutral|negative|interested|hesitant>",
    "mood_detail": "<tek cumle: musterinin ruh hali aciklamasi>",
    "signals": [
        {{"type": "<positive|objection|info>", "text": "<sinyal aciklamasi>"}},
    ],
    "keywords": [
        {{"word": "<anahtar kelime>", "sentiment": "<positive|negative|neutral>"}},
    ],
    "summary": "<2-3 cumle: gorusmenin genel durumu ve oneriler>"
}}

KURALLAR:
- purchase_intent: Musteri paket sorduysa 40+, fiyat kabul ettiyse 70+, bilgi veriyorsa 80+, sadece selamlasma ise 15-25
- signals: En fazla 4 sinyal ver
- keywords: En fazla 6 kelime ver
- Turkce yaz"""

    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Sen bir satis analiz AI'sin. Sadece gecerli JSON dondur, baska bir sey yazma."},
                {"role": "user", "content": analysis_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
            response_format={"type": "json_object"},
        )
        result = _json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        logger.error(f"Live analysis error: {e}")
        return {
            "purchase_intent": 0,
            "intent_reason": "Analiz yapilamadi",
            "mood": "neutral",
            "mood_detail": str(e),
            "signals": [],
            "keywords": [],
            "summary": "Analiz sirasinda hata olustu.",
        }


@app.get("/api/dashboard-kpis", response_class=HTMLResponse)
async def dashboard_kpis(db=Depends(get_db)):
    """Return KPI card HTML fragment for HTMX auto-refresh."""
    from datetime import datetime, timezone
    from sqlalchemy import func
    from db.models import CallSession, Application, Customer

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_calls = db.query(func.count(CallSession.id)).filter(CallSession.started_at >= today_start).scalar() or 0
    today_applications = db.query(func.count(Application.id)).filter(Application.created_at >= today_start).scalar() or 0
    active_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "active").scalar() or 0
    total_calls = db.query(func.count(CallSession.id)).scalar() or 0
    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    total_packages = db.query(func.count(Package.id)).filter(Package.is_active == True).scalar() or 0
    completed_calls = db.query(func.count(CallSession.id)).filter(CallSession.status == "completed").scalar() or 0
    completed_applications = db.query(func.count(Application.id)).filter(Application.status == "completed").scalar() or 0
    success_rate = round((completed_calls / total_calls * 100), 1) if total_calls > 0 else 0
    avg_duration_val = db.query(func.avg(CallSession.duration_seconds)).filter(CallSession.duration_seconds > 0).scalar()
    avg_duration = round(float(avg_duration_val), 1) if avg_duration_val else 0
    avg_mins = int(avg_duration // 60)
    avg_secs = int(avg_duration % 60)

    recontact_count = db.query(func.count(CallSession.id)).filter(
        CallSession.recontact_priority.in_(["high", "medium"]),
        CallSession.recontact_score > 0,
    ).scalar() or 0

    html = f"""
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#3b82f6;"></div>
            <div class="stat-icon" style="background:#eff6ff;color:#3b82f6;"><i class="bi bi-telephone-fill"></i></div>
            <div class="stat-label">Bugun Cagri</div>
            <div class="stat-value">{today_calls}</div>
            <div class="stat-change"><i class="bi bi-circle-fill text-success" style="font-size:0.5rem"></i> {active_calls} aktif</div>
        </div>
    </div>
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#10b981;"></div>
            <div class="stat-icon" style="background:#ecfdf5;color:#10b981;"><i class="bi bi-file-earmark-check-fill"></i></div>
            <div class="stat-label">Bugun Basvuru</div>
            <div class="stat-value">{today_applications}</div>
            <div class="stat-change">basvuru alindi</div>
        </div>
    </div>
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#8b5cf6;"></div>
            <div class="stat-icon" style="background:#f5f3ff;color:#8b5cf6;"><i class="bi bi-bullseye"></i></div>
            <div class="stat-label">Donusum</div>
            <div class="stat-value">%{success_rate}</div>
            <div class="stat-change">{completed_applications} basarili</div>
        </div>
    </div>
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#06b6d4;"></div>
            <div class="stat-icon" style="background:#ecfeff;color:#06b6d4;"><i class="bi bi-clock-fill"></i></div>
            <div class="stat-label">Ort. Sure</div>
            <div class="stat-value">{avg_mins} dk {avg_secs} sn</div>
            <div class="stat-change">{total_calls} toplam cagri</div>
        </div>
    </div>
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#f59e0b;"></div>
            <div class="stat-icon" style="background:#fff7ed;color:#f59e0b;"><i class="bi bi-telephone-forward-fill"></i></div>
            <div class="stat-label">Tekrar Ara</div>
            <div class="stat-value">{recontact_count}</div>
            <div class="stat-change">kisi bekliyor</div>
        </div>
    </div>
    <div class="col-xl-2 col-md-4 col-6">
        <div class="stat-card">
            <div class="stat-glow" style="background:#ec4899;"></div>
            <div class="stat-icon" style="background:#fdf2f8;color:#ec4899;"><i class="bi bi-people-fill"></i></div>
            <div class="stat-label">Musteri</div>
            <div class="stat-value">{total_customers}</div>
            <div class="stat-change">{total_packages} paket</div>
        </div>
    </div>
    """
    return HTMLResponse(content=html)


@app.get("/api/dashboard-stats")
async def dashboard_stats(db=Depends(get_db)):
    from datetime import datetime, timezone
    from sqlalchemy import func
    from db.models import CallSession, Application, Customer
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "today_calls": db.query(func.count(CallSession.id)).filter(CallSession.started_at >= today_start).scalar() or 0,
        "today_applications": db.query(func.count(Application.id)).filter(Application.created_at >= today_start).scalar() or 0,
        "active_calls": db.query(func.count(CallSession.id)).filter(CallSession.status == "active").scalar() or 0,
        "total_customers": db.query(func.count(Customer.id)).scalar() or 0,
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    from auth import verify_session
    if verify_session(request):
        return RedirectResponse("/admin/", status_code=303)
    from fastapi.templating import Jinja2Templates
    tpl = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "admin", "templates"))
    return tpl.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login(request: Request):
    from auth import ADMIN_USERNAME, ADMIN_PASSWORD, create_session
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        token = create_session(username)
        response = RedirectResponse("/admin/", status_code=303)
        response.set_cookie("session_token", token, httponly=True, max_age=86400)
        return response
    from fastapi.templating import Jinja2Templates
    tpl = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "admin", "templates"))
    return tpl.TemplateResponse("login.html", {"request": request, "error": "Kullanici adi veya sifre hatali"})


@app.get("/logout")
async def logout_route(request: Request):
    from auth import logout
    token = request.cookies.get("session_token")
    if token:
        logout(token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
    <head><title>Digiturk Bayi AI Voice Agent</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>Digiturk Bayi AI Voice Agent</h1>
        <p>Sistem calisiyor.</p>
        <ul style="list-style:none; padding:0;">
            <li><a href="/test-call">Sesli Test (Tarayici)</a></li>
            <li><a href="/admin/">Admin Panel</a></li>
            <li><a href="/health">Health Check</a></li>
        </ul>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "service": "digiturk-voice-agent"}


# --- Twilio Webhooks ---

@app.api_route("/twilio/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming Twilio call - return TwiML to connect to Media Stream."""
    form = await request.form()
    caller = form.get("From", "unknown")
    call_sid = form.get("CallSid", "unknown")
    logger.info(f"Incoming call from {caller} (SID: {call_sid})")

    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")

    response = VoiceResponse()
    response.say("Lutfen bekleyiniz, sizi bagliyorum.", language="tr-TR")

    connect = Connect()
    stream = connect.stream(url=f"{ws_url}/twilio/media-stream")
    stream.parameter(name="callerPhone", value=caller)
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


@app.websocket("/twilio/media-stream")
async def media_stream(websocket: WebSocket):
    """WebSocket endpoint for Twilio Media Streams."""
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connected")

    bridge = TwilioOpenAIBridge(websocket)
    await bridge.handle()

    logger.info("Twilio Media Stream WebSocket closed")


# --- Browser Test Call ---

@app.get("/test-call", response_class=HTMLResponse)
async def test_call_page(request: Request):
    """Browser-based voice test page - no Twilio needed."""
    from fastapi.templating import Jinja2Templates
    tpl = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "admin", "templates"))
    return tpl.TemplateResponse("test_call.html", {"request": request})


@app.websocket("/test-call/ws")
async def test_call_ws(websocket: WebSocket):
    """WebSocket endpoint for browser-based voice testing."""
    await websocket.accept()
    logger.info("Browser test call WebSocket connected")

    bridge = BrowserGeminiBridge(websocket)
    await bridge.handle()

    logger.info("Browser test call WebSocket closed")


# --- Application Link ---

@app.get("/apply", response_class=HTMLResponse)
async def apply_page(token: str = "", db=Depends(get_db)):
    """Application completion page (linked from SMS)."""
    if not token:
        return HTMLResponse("<h1>Gecersiz link</h1>", status_code=400)

    app_svc = ApplicationService(db)
    application = app_svc.verify_token(token)

    if not application:
        return HTMLResponse("""
        <html><body style="font-family:sans-serif;text-align:center;padding:50px;">
        <h1>Link suresi dolmus veya gecersiz</h1>
        <p>Lutfen tekrar arayarak yeni bir basvuru olusturun.</p>
        </body></html>
        """, status_code=410)

    # Update status to link_sent (opened)
    application.status = "link_sent"
    db.commit()

    return f"""
    <html>
    <head>
        <title>Digiturk Basvuru</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background:#f4f6f9;">
        <div class="container" style="max-width:500px; margin-top:40px;">
            <div class="card">
                <div class="card-header bg-primary text-white text-center">
                    <h4>Digiturk Basvuru</h4>
                </div>
                <div class="card-body">
                    <p class="text-success"><strong>Basvurunuz alindi!</strong></p>
                    <p>Paket: <strong>{application.package.name if application.package else '-'}</strong></p>
                    <p>Bu demo sayfasidir. Gercek uretimde burada odeme/sozlesme adimi yer alacaktir.</p>
                    <hr>
                    <form method="POST" action="/apply/complete?token={token}">
                        <button type="submit" class="btn btn-success btn-lg w-100">
                            Basvuruyu Tamamla
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@app.post("/apply/complete", response_class=HTMLResponse)
async def apply_complete(token: str = "", db=Depends(get_db)):
    """Complete the application."""
    app_svc = ApplicationService(db)
    application = app_svc.verify_token(token)

    if not application:
        return HTMLResponse("<h1>Gecersiz link</h1>", status_code=400)

    application.status = "completed"
    db.commit()

    return """
    <html>
    <head>
        <title>Basvuru Tamamlandi</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background:#f4f6f9;">
        <div class="container" style="max-width:500px; margin-top:40px;">
            <div class="card">
                <div class="card-body text-center">
                    <h2 class="text-success mb-3">Basvurunuz Tamamlandi!</h2>
                    <p>En kisa surede sizinle iletisime gecilegektir.</p>
                    <p>Digiturk'u tercih ettiginiz icin tesekkur ederiz.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    uvicorn.run("server:app", host=host, port=port, reload=True)
