"""Browser <-> Gemini Live API bridge (native audio-to-audio)."""
import os
import json
import asyncio
import logging
import time
from datetime import datetime, timezone

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from state_machine import CallContext, CallState
from prompts import build_system_prompt
from validators import validate_tckn, normalize_phone, parse_date
from db.database import SessionLocal
from db.models import CallSession, Customer
from services.catalog_service import CatalogService
from services.customer_service import CustomerService
from services.application_service import ApplicationService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)

# Gemini Live API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-native-audio-latest")
GEMINI_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
    f"?key={GEMINI_API_KEY}"
)


class BrowserGeminiBridge:
    """Bridges audio between browser and Gemini Live API (native audio-to-audio)."""

    def __init__(self, browser_ws: WebSocket):
        self.browser_ws = browser_ws
        self.gemini_ws = None
        self.ctx = CallContext()
        self.db = SessionLocal()
        self.call_session = None
        self._browser_closed = False
        self._setup_complete = False
        self._ai_transcript_buffer = ""
        self._user_transcript_buffer = ""
        self._user_speech_end_time = 0  # for latency measurement
        self._first_audio_response_logged = False
        self._conversation_transcript = []
        # Silence detection
        self._silence_check_task = None
        self._last_user_audio_time = 0
        self._ai_turn_complete_time = 0
        self._silence_warnings = 0
        self._ai_is_speaking = False

    async def handle(self):
        try:
            if not GEMINI_API_KEY:
                await self._send_browser({"type": "error", "message": "GEMINI_API_KEY ayarlanmamış."})
                return

            async with websockets.connect(
                GEMINI_LIVE_URL,
                ping_interval=20,
                ping_timeout=20,
            ) as gemini_ws:
                self.gemini_ws = gemini_ws
                await self._configure_session()
                await self._create_call_session()

                await asyncio.gather(
                    self._listen_browser(),
                    self._listen_gemini(),
                    self._silence_monitor(),
                )
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"Gemini connection failed: {e}")
            await self._send_browser({"type": "error", "message": f"Gemini bağlantı hatası: {e}"})
        except Exception as e:
            logger.error(f"Bridge error: {e}", exc_info=True)
            await self._send_browser({"type": "error", "message": str(e)})
        finally:
            await self._finalize_call()

    async def _send_browser(self, data: dict):
        if self._browser_closed:
            return
        try:
            await self.browser_ws.send_json(data)
        except Exception:
            self._browser_closed = True

    # ── Gemini Session ────────────────────────────────────────────────

    async def _configure_session(self):
        catalog_summary = self._get_catalog_summary()
        system_prompt = build_system_prompt(self.ctx, catalog_summary)

        setup_msg = {
            "setup": {
                "model": f"models/{GEMINI_MODEL}",
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "languageCode": "tr-TR",
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Kore",
                            },
                        },
                    },
                    "thinkingConfig": {
                        "thinkingBudget": 0,
                    },
                },
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                },
                "tools": [{
                    "function_declarations": [
                        {
                            "name": "list_packages",
                            "description": "Mevcut Digiturk paketlerini listeler",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "category": {
                                        "type": "string",
                                        "enum": ["kampanyali_paketler", "kutulu_paketler", "internet_paketleri"],
                                        "description": "Paket kategorisi filtresi"
                                    }
                                }
                            }
                        },
                        {
                            "name": "get_package",
                            "description": "Belirli bir paketin detaylarini getirir",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "package_id": {"type": "string", "description": "Paket ID"}
                                },
                                "required": ["package_id"]
                            }
                        },
                        {
                            "name": "select_package",
                            "description": "Musteri paketi VE odeme turunu onayladiktan sonra cagir. Paketi ve odemeyi birlikte kaydet. Odeme turu sorulmadan CAGIRMA.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "package_id": {"type": "string", "description": "Secilen paket ID"},
                                    "payment_type": {"type": "string", "description": "taksit veya faturali"},
                                    "team": {"type": "string", "description": "Secilen takim (varsa)"}
                                },
                                "required": ["package_id", "payment_type"]
                            }
                        },
                        {
                            "name": "validate_tckn",
                            "description": "TC Kimlik Numarasini dogrular. SADECE musterinin SOZEL OLARAK soyledigi 11 hanelik numarayi gonder. Kendin numara UYDURMA. Once musteriden TC iste, musteri soylesin, sen kaydet, 11 hane olunca cagir.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "tckn": {"type": "string", "description": "11 haneli TC Kimlik Numarasi, eksik hane olmamali"}
                                },
                                "required": ["tckn"]
                            }
                        },
                        {
                            "name": "save_customer",
                            "description": "Musteri bilgilerini kaydeder",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Ad"},
                                    "surname": {"type": "string", "description": "Soyad"},
                                    "tckn": {"type": "string", "description": "TC Kimlik"},
                                    "birth_date": {"type": "string", "description": "Dogum tarihi GG.AA.YYYY"},
                                    "phone": {"type": "string", "description": "Telefon numarasi"},
                                    "city": {"type": "string", "description": "Il"},
                                    "district": {"type": "string", "description": "Ilce"},
                                    "neighborhood": {"type": "string", "description": "Mahalle"},
                                    "street": {"type": "string", "description": "Sokak"},
                                    "building_no": {"type": "string", "description": "Bina no"},
                                    "apartment_no": {"type": "string", "description": "Daire no"}
                                },
                                "required": ["name", "surname", "tckn", "birth_date", "phone"]
                            }
                        },
                        {
                            "name": "create_application",
                            "description": "Basvuru olusturur ve SMS ile link gonderir. SADECE save_customer basarili olduktan sonra cagir.",
                            "parameters": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                }],
            }
        }
        await self.gemini_ws.send(json.dumps(setup_msg))
        logger.info(f"Gemini setup sent (model={GEMINI_MODEL})")

        # Wait for setupComplete
        async for message in self.gemini_ws:
            data = json.loads(message)
            if "setupComplete" in data:
                self._setup_complete = True
                logger.info("Gemini ready")
                break

        # Trigger initial greeting
        await self.gemini_ws.send(json.dumps({
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text": "Merhaba"}]}],
                "turnComplete": True,
            }
        }))

    async def _listen_browser(self):
        """Forward browser audio to Gemini."""
        try:
            while True:
                message = await self.browser_ws.receive_text()
                data = json.loads(message)

                if data.get("type") == "audio" and self._setup_complete:
                    audio_b64 = data.get("audio", "")
                    if audio_b64 and self.gemini_ws and self.gemini_ws.state.name == "OPEN":
                        self._last_user_audio_time = time.monotonic()
                        await self.gemini_ws.send(json.dumps({
                            "realtimeInput": {
                                "audio": {
                                    "data": audio_b64,
                                    "mimeType": "audio/pcm;rate=16000",
                                }
                            }
                        }))

        except WebSocketDisconnect:
            self._browser_closed = True
            logger.info("Browser WebSocket disconnected")
        except websockets.exceptions.ConnectionClosed:
            self._browser_closed = True
            logger.info("Gemini connection lost during audio send")
        except Exception as e:
            self._browser_closed = True
            logger.error(f"Browser listener error: {e}", exc_info=True)

    async def _listen_gemini(self):
        """Handle Gemini Live API responses — forward audio to browser."""
        try:
            async for message in self.gemini_ws:
                data = json.loads(message)

                if "serverContent" in data:
                    sc = data["serverContent"]

                    # Audio output — forward directly to browser
                    if "modelTurn" in sc:
                        self._ai_is_speaking = True
                        parts = sc["modelTurn"].get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                audio_b64 = part["inlineData"].get("data", "")
                                if audio_b64:
                                    if self._user_speech_end_time and not self._first_audio_response_logged:
                                        latency_ms = int((time.monotonic() - self._user_speech_end_time) * 1000)
                                        logger.info(f"⚡ AI response latency: {latency_ms}ms (user speech done → first AI audio)")
                                        self._first_audio_response_logged = True
                                    await self._send_browser({"type": "audio", "audio": audio_b64})

                    # Output transcription — accumulate
                    if "outputTranscription" in sc:
                        text = sc["outputTranscription"].get("text", "")
                        if text:
                            self._ai_transcript_buffer += text

                    # Input transcription — user speech ended, start latency timer
                    if "inputTranscription" in sc:
                        text = sc["inputTranscription"].get("text", "")
                        if text:
                            self._user_transcript_buffer += text
                            # Each transcription update = user still/just finished speaking
                            self._user_speech_end_time = time.monotonic()
                            self._first_audio_response_logged = False
                            logger.info(f"🎤 User speech detected: '{text.strip()}'")

                    # Turn complete — flush transcripts, start silence timer
                    if sc.get("turnComplete"):
                        self._user_speech_end_time = time.monotonic()
                        self._first_audio_response_logged = False
                        # Only start silence timer if AI actually spoke audio
                        if self._ai_is_speaking:
                            self._ai_turn_complete_time = time.monotonic()
                            self._silence_warnings = 0
                        self._ai_is_speaking = False
                        if self._ai_transcript_buffer:
                            # De-duplicate: check if text is repeated
                            text = self._ai_transcript_buffer.strip()
                            half = len(text) // 2
                            if half > 10 and text[:half] == text[half:]:
                                text = text[:half]
                            logger.info(f"AI said: {text}")
                            await self._send_browser({"type": "transcript_ai", "text": text})
                            self._conversation_transcript.append(f"AI: {text}")
                            self._ai_transcript_buffer = ""
                        if self._user_transcript_buffer:
                            logger.info(f"User said: {self._user_transcript_buffer}")
                            await self._send_browser({"type": "transcript_user", "text": self._user_transcript_buffer})
                            self._conversation_transcript.append(f"Müşteri: {self._user_transcript_buffer}")
                            self._user_transcript_buffer = ""

                    # Interrupted by user — user started speaking
                    if sc.get("interrupted"):
                        logger.info("Gemini interrupted — user speaking")
                        self._user_speech_end_time = time.monotonic()
                        self._first_audio_response_logged = False
                        self._ai_is_speaking = False
                        self._silence_warnings = 0
                        self._ai_turn_complete_time = 0
                        if self._ai_transcript_buffer:
                            await self._send_browser({"type": "transcript_ai", "text": self._ai_transcript_buffer + "..."})
                            self._ai_transcript_buffer = ""
                        self._user_transcript_buffer = ""
                        await self._send_browser({"type": "interrupted"})

                # Tool calls
                elif "toolCall" in data:
                    await self._handle_tool_call(data["toolCall"])

                # Tool call cancellation
                elif "toolCallCancellation" in data:
                    logger.info("Gemini tool call cancelled")
                    self._ai_transcript_buffer = ""
                    await self._send_browser({"type": "clear_audio"})

        except websockets.exceptions.ConnectionClosed as e:
            logger.info(f"Gemini WebSocket closed: {e}")
        except Exception as e:
            logger.error(f"Gemini listener error: {e}", exc_info=True)

    # ── Function calling ──────────────────────────────────────────────

    async def _handle_tool_call(self, tool_call: dict):
        function_calls = tool_call.get("functionCalls", [])
        if not function_calls:
            return

        # Process only the FIRST function call — prevent chain-calling
        fc = function_calls[0]
        fn_name = fc.get("name", "")
        fc_id = fc.get("id", "")
        args = fc.get("args", {})

        if len(function_calls) > 1:
            logger.warning(f"Gemini sent {len(function_calls)} function calls at once, processing only first: {fn_name}")

        logger.info(f"Function call: {fn_name}({args})")
        await self._send_browser({"type": "function_call", "name": fn_name, "args": args})

        result = await self._execute_function(fn_name, args)

        function_responses = [{
            "id": fc_id,
            "name": fn_name,
            "response": result,
        }]

        # If there were extra function calls, return errors for them
        for extra_fc in function_calls[1:]:
            function_responses.append({
                "id": extra_fc.get("id", ""),
                "name": extra_fc.get("name", ""),
                "response": {"error": "Tek seferde sadece bir fonksiyon cagrilabilir. Sonraki adima gec."},
            })

        await self.gemini_ws.send(json.dumps({
            "toolResponse": {
                "functionResponses": function_responses,
            }
        }))

    async def _execute_function(self, fn_name: str, args: dict) -> dict:
        try:
            if fn_name == "list_packages":
                catalog = CatalogService(self.db)
                packages = catalog.list_packages(category=args.get("category"))
                return {"packages": packages}

            elif fn_name == "get_package":
                catalog = CatalogService(self.db)
                pkg = catalog.get_package(args.get("package_id", ""))
                return {"package": pkg} if pkg else {"error": "Paket bulunamadı"}

            elif fn_name == "select_package":
                return await self._select_package(args)

            elif fn_name == "validate_tckn":
                tckn_raw = args.get("tckn", "").strip().replace(" ", "")
                # Uydurma TC koruması
                fake_patterns = ["12345678901", "11111111111", "00000000000", "99999999999", "12345678900"]
                if tckn_raw in fake_patterns:
                    logger.warning(f"validate_tckn rejected FAKE tckn: {tckn_raw}")
                    return {"valid": False, "error": "Bu numara gecersiz. Musteriden gercek TC kimlik numarasini iste. Kendin numara UYDURMA."}
                if len(tckn_raw) != 11:
                    logger.warning(f"validate_tckn called with {len(tckn_raw)} digits: {tckn_raw}")
                    return {"valid": False, "error": f"TCKN {len(tckn_raw)} hane, 11 hane olmali. Musteriden eksik rakamlari al."}
                is_valid, error = validate_tckn(tckn_raw)
                if is_valid:
                    self.ctx.tckn = tckn_raw
                    logger.info(f"TCKN validated: {tckn_raw[:3]}***")
                    return {"valid": True}
                else:
                    self.ctx.tckn_attempts += 1
                    logger.warning(f"TCKN invalid: {error}")
                    return {"valid": False, "error": error}

            elif fn_name == "save_customer":
                return await self._save_customer(args)

            elif fn_name == "create_application":
                return await self._create_application()

            else:
                return {"error": f"Bilinmeyen fonksiyon: {fn_name}"}

        except Exception as e:
            logger.error(f"Function execution error: {e}", exc_info=True)
            return {"error": str(e)}

    async def _select_package(self, args: dict) -> dict:
        package_id = args.get("package_id", "")
        catalog = CatalogService(self.db)
        pkg = catalog.get_package(package_id)
        if not pkg:
            return {"error": "Paket bulunamadı"}

        self.ctx.selected_package_id = package_id
        self.ctx.selected_package_name = pkg["name"]
        self.ctx.selected_category = pkg["category"]
        self.ctx.selected_delivery = pkg["delivery"]
        if args.get("payment_type"):
            self.ctx.selected_payment_type = args["payment_type"]
        if args.get("team"):
            self.ctx.selected_team = args["team"]

        logger.info(f"Package selected: {pkg['name']} ({package_id})")
        await self._send_browser({
            "type": "package_selected",
            "package_id": package_id,
            "package_name": pkg["name"],
        })

        return {"status": "ok", "package": pkg["name"]}

    async def _save_customer(self, args: dict) -> dict:
        is_valid, err = validate_tckn(args.get("tckn", ""))
        if not is_valid:
            return {"error": f"TCKN hatalı: {err}"}

        phone = args.get("phone", "+905001234567")
        normalized_phone, err = normalize_phone(phone)
        if not normalized_phone:
            return {"error": f"Telefon hatalı: {err}"}

        birth_date = None
        if args.get("birth_date"):
            parsed, err = parse_date(args["birth_date"])
            if not parsed:
                return {"error": f"Tarih hatalı: {err}"}
            birth_date = parsed

        customer_svc = CustomerService(self.db)
        customer = customer_svc.create_customer(
            name=args["name"],
            surname=args["surname"],
            phone=normalized_phone,
            tckn=args.get("tckn"),
            birth_date=birth_date,
            city=args.get("city") or self.ctx.city,
            district=args.get("district") or self.ctx.district,
            neighborhood=args.get("neighborhood") or self.ctx.neighborhood,
            street=args.get("street") or self.ctx.street,
            building_no=args.get("building_no") or self.ctx.building_no,
            apartment_no=args.get("apartment_no") or self.ctx.apartment_no,
        )
        self.db.commit()
        self.ctx.phone = normalized_phone

        if self.call_session:
            self.call_session.customer_id = customer.id
            self.db.commit()

        return {"customer_id": str(customer.id), "status": "saved"}

    async def _create_application(self) -> dict:
        logger.info(f"=== CREATE APPLICATION START === package={self.ctx.selected_package_id}, phone={self.ctx.phone}")

        if not self.ctx.selected_package_id:
            logger.error("CREATE APPLICATION FAILED: Paket seçilmedi!")
            return {"error": "Paket seçilmedi. Önce select_package çağırmalısın."}

        catalog = CatalogService(self.db)
        pkg = catalog.get_package(self.ctx.selected_package_id)
        if not pkg:
            logger.error(f"CREATE APPLICATION FAILED: Paket bulunamadı: {self.ctx.selected_package_id}")
            return {"error": "Paket bulunamadı"}

        customer_svc = CustomerService(self.db)
        customer = customer_svc.find_by_phone(self.ctx.phone or "+905001234567")
        if not customer:
            logger.error(f"CREATE APPLICATION FAILED: Müşteri bulunamadı, phone={self.ctx.phone}")
            return {"error": "Müşteri bulunamadı. Önce save_customer çağır."}

        try:
            app_svc = ApplicationService(self.db)
            result = app_svc.create_application(
                customer_id=customer.id,
                package_id=pkg["id"],
                payment_type=self.ctx.selected_payment_type or "credit_card_installment_12",
                delivery=self.ctx.selected_delivery or "kutusuz",
                team=self.ctx.selected_team,
            )

            sms_svc = SMSService(self.db)
            sms_svc.send_sms(
                application_id=result["application_id"],
                to_phone=self.ctx.phone or "+905001234567",
                template="apply_link",
                params={"apply_url": result["apply_url"]},
            )
            self.db.commit()

            self.ctx.application_id = result["application_id"]
            self.ctx.apply_url = result["apply_url"]

            if self.call_session:
                self.call_session.application_id = result["application_id"]
                self.db.commit()

            logger.info(f"=== CREATE APPLICATION SUCCESS === app_id={result['application_id']}, url={result['apply_url']}, sms_sent=True")

            # Schedule auto-close after AI says goodbye
            asyncio.create_task(self._auto_close_after_application())

            return {
                "application_id": result["application_id"],
                "apply_url": result["apply_url"],
                "sms_sent": True
            }
        except Exception as e:
            logger.error(f"=== CREATE APPLICATION EXCEPTION === {e}", exc_info=True)
            return {"error": f"Başvuru oluşturulamadı: {str(e)}"}

    def _get_catalog_summary(self) -> str:
        catalog = CatalogService(self.db)
        packages = catalog.list_packages()
        if not packages:
            return "Paket kataloğu boş."
        lines = []
        for pkg in packages:
            prices = ", ".join(
                f"{p['payment_type']}: {p['amount_monthly']} {p['currency']}/ay"
                for p in pkg["pricing"]
            )
            team_info = f" (Takımlar: {', '.join(pkg['teams_supported'])})" if pkg["team_required"] else ""
            lines.append(f"- {pkg['name']} [{pkg['package_id']}]: {prices}{team_info}")
        return "\n".join(lines)

    async def _silence_monitor(self):
        """Monitor user silence after AI finishes speaking.
        If user doesn't respond within 6s, prompt them. After 3 attempts, end call."""
        SILENCE_TIMEOUT = 8.0
        MAX_WARNINGS = 3

        try:
            while not self._browser_closed:
                await asyncio.sleep(2)

                # Only check when AI finished speaking and waiting for user
                if (self._ai_turn_complete_time <= 0
                        or self._ai_is_speaking
                        or self._browser_closed):
                    continue

                # If Gemini got interrupted since last turn complete, user is speaking — skip
                if self._user_speech_end_time > self._ai_turn_complete_time:
                    self._silence_warnings = 0
                    continue

                elapsed = time.monotonic() - self._ai_turn_complete_time

                if elapsed >= SILENCE_TIMEOUT * (self._silence_warnings + 1):
                    self._silence_warnings += 1
                    logger.info(f"Silence monitor: warning {self._silence_warnings}/{MAX_WARNINGS}, elapsed={elapsed:.1f}s")

                    if self._silence_warnings >= MAX_WARNINGS:
                        logger.info("Silence monitor: max warnings, ending call")
                        await self._send_silence_prompt(
                            "Sesinizi alamıyorum, görüşmeyi sonlandırıyorum. İyi günler dilerim."
                        )
                        await asyncio.sleep(4)
                        await self._send_browser({"type": "call_ended", "reason": "Sessizlik - bağlantı kesildi"})
                        self._browser_closed = True
                        break
                    elif self._silence_warnings == 1:
                        await self._send_silence_prompt("Orada mısınız? Sesinizi alamıyorum.")
                    elif self._silence_warnings == 2:
                        await self._send_silence_prompt("Sesiniz gelmiyor, beni duyabiliyor musunuz?")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Silence monitor error: {e}")

    async def _auto_close_after_application(self):
        """After application is created, wait for AI to finish speaking + 10s silence, then close."""
        try:
            # First wait for AI to finish speaking
            while not self._browser_closed:
                await asyncio.sleep(1)
                if not self._ai_is_speaking and self._ai_turn_complete_time > 0:
                    break

            # Now wait 10 seconds of silence after AI finished
            if not self._browser_closed:
                await asyncio.sleep(10)

            if not self._browser_closed:
                logger.info("Auto-closing call after successful application")
                await self._send_browser({"type": "call_ended", "reason": "Başvuru tamamlandı"})
                self._browser_closed = True
        except Exception as e:
            logger.error(f"Auto-close error: {e}")

    async def _send_silence_prompt(self, text: str):
        """Send a text prompt to Gemini to make it speak a silence warning."""
        try:
            if self.gemini_ws and self.gemini_ws.state.name == "OPEN":
                await self.gemini_ws.send(json.dumps({
                    "clientContent": {
                        "turns": [{"role": "user", "parts": [{"text": f"[SİSTEM: Müşteri sessiz. Şunu söyle: '{text}']"}]}],
                        "turnComplete": True,
                    }
                }))
                # Reset turn complete time so next silence check starts fresh
                self._ai_turn_complete_time = time.monotonic()
        except Exception as e:
            logger.error(f"Silence prompt error: {e}")

    async def _create_call_session(self):
        try:
            self.call_session = CallSession(
                twilio_call_sid=f"browser-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                caller_phone="browser-test",
                status="active",
            )
            self.db.add(self.call_session)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to create call session: {e}")
            self.db.rollback()

    async def _finalize_call(self):
        try:
            if self.call_session:
                now = datetime.now(timezone.utc)
                self.call_session.ended_at = now
                self.call_session.state_history = self.ctx.state_history
                self.call_session.flags = self.ctx.flags
                if self.ctx.state == CallState.CLOSE_FAIL:
                    self.call_session.status = "failed"
                elif self.ctx.state == CallState.CLOSE_SUCCESS:
                    self.call_session.status = "completed"
                self.call_session.conversation_summary = self.ctx.get_summary()

                # New fields
                if self.call_session.started_at:
                    delta = now - self.call_session.started_at
                    self.call_session.duration_seconds = int(delta.total_seconds())
                self.call_session.channel = "browser"
                self.call_session.dropped_at_state = self.ctx.state.value
                self.call_session.conversation_transcript = "\n".join(self._conversation_transcript)

                # Update customer stats if customer exists
                if self.call_session.customer_id:
                    customer = self.db.query(Customer).filter(
                        Customer.id == self.call_session.customer_id
                    ).first()
                    if customer:
                        customer.total_calls = (customer.total_calls or 0) + 1
                        customer.last_call_at = now
                        if customer.total_calls == 1:
                            customer.customer_segment = "new"
                        elif self.call_session.status == "completed":
                            customer.customer_segment = "converted"
                        else:
                            customer.customer_segment = "returning"

                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to finalize call: {e}")
            self.db.rollback()
        finally:
            self.db.close()
