"""FastAPI main application - Twilio webhooks, WebSocket endpoint, admin panel."""
import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from twilio.twiml.voice_response import VoiceResponse, Connect

from db.database import engine, Base, get_db, SessionLocal
from db.models import Package
from admin.routes import router as admin_router
from websocket_handler import TwilioOpenAIBridge
from browser_bridge import BrowserOpenAIBridge
from services.application_service import ApplicationService

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

    bridge = BrowserOpenAIBridge(websocket)
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
