"""Browser <-> OpenAI Realtime API bridge (native audio or ElevenLabs TTS)."""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from state_machine import CallContext, CallState
from prompts import build_system_prompt, OPENAI_TOOLS
from validators import validate_tckn, normalize_phone, parse_date
from db.database import SessionLocal
from db.models import CallSession
from services.catalog_service import CatalogService
from services.customer_service import CustomerService
from services.application_service import ApplicationService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)

# ── Mode toggle: set to True to use ElevenLabs TTS, False for OpenAI native audio ──
USE_ELEVENLABS = False

# OpenAI Realtime API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_OPENAI_MODEL = "gpt-realtime-mini" if USE_ELEVENLABS else "gpt-realtime-1.5"
OPENAI_REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={_OPENAI_MODEL}"

# ElevenLabs TTS - flash model for lowest latency (disabled when USE_ELEVENLABS=False)
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "cgSgspJ2msm6clMCkdW9")
ELEVENLABS_MODEL = "eleven_flash_v2_5"


def _el_ws_url():
    return (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream-input"
        f"?model_id={ELEVENLABS_MODEL}"
        f"&output_format=pcm_24000"
        f"&optimize_streaming_latency=4"
    )


class BrowserOpenAIBridge:
    """Bridges audio between browser WebSocket, OpenAI Realtime API (text), and ElevenLabs TTS."""

    def __init__(self, browser_ws: WebSocket):
        self.browser_ws = browser_ws
        self.openai_ws = None
        self.elevenlabs_ws = None
        self.ctx = CallContext()
        self.db = SessionLocal()
        self.call_session = None
        self._tts_receiver_task = None
        self._is_speaking = False
        self._current_text_buffer = ""
        self._browser_closed = False

    async def handle(self):
        try:
            if not OPENAI_API_KEY or OPENAI_API_KEY == "sk-...":
                await self._send_browser({"type": "error", "message": "OPENAI_API_KEY ayarlanmamis."})
                return

            if USE_ELEVENLABS and not ELEVENLABS_API_KEY:
                await self._send_browser({"type": "error", "message": "ELEVENLABS_API_KEY ayarlanmamis."})
                return

            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
            async with websockets.connect(
                OPENAI_REALTIME_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            ) as openai_ws:
                self.openai_ws = openai_ws
                await self._configure_session()
                await self._create_call_session()

                await asyncio.gather(
                    self._listen_browser(),
                    self._listen_openai(),
                )
        except websockets.exceptions.InvalidStatusCode as e:
            logger.error(f"OpenAI connection failed: {e}")
            await self._send_browser({"type": "error", "message": f"OpenAI baglanti hatasi: {e}"})
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

    async def _configure_session(self):
        catalog_summary = self._get_catalog_summary()
        system_prompt = build_system_prompt(self.ctx, catalog_summary)

        modalities = ["text"] if USE_ELEVENLABS else ["audio"]
        model = "gpt-realtime-mini" if USE_ELEVENLABS else "gpt-realtime-1.5"

        session_config = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": model,
                "output_modalities": modalities,
                "instructions": system_prompt,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.99,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 400,
                        },
                        "transcription": {"model": "whisper-1"},
                    },
                    "output": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "voice": "marin",
                    },
                },
                "tools": OPENAI_TOOLS,
                "tool_choice": "auto",
            },
        }
        await self.openai_ws.send(json.dumps(session_config))
        logger.info(f"OpenAI session configured ({model}, modalities={modalities})")

        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    async def _listen_browser(self):
        try:
            while True:
                message = await self.browser_ws.receive_text()
                data = json.loads(message)

                if data.get("type") == "audio":
                    audio_b64 = data.get("audio", "")
                    if audio_b64:
                        await self.openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": audio_b64,
                        }))

        except WebSocketDisconnect:
            self._browser_closed = True
            logger.info("Browser WebSocket disconnected")
        except Exception as e:
            self._browser_closed = True
            logger.error(f"Browser listener error: {e}", exc_info=True)

    async def _listen_openai(self):
        try:
            async for message in self.openai_ws:
                event = json.loads(message)
                event_type = event.get("type", "")

                if event_type == "session.created":
                    mode = "ElevenLabs TTS" if USE_ELEVENLABS else "native audio"
                    logger.info(f"OpenAI session created ({mode})")

                # ── OpenAI native audio output (when USE_ELEVENLABS=False) ──
                elif event_type in ("response.audio.delta", "response.output_audio.delta") and not USE_ELEVENLABS:
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        await self._send_browser({"type": "audio", "audio": audio_b64})

                # Text delta - stream to ElevenLabs (only when USE_ELEVENLABS=True)
                elif event_type == "response.output_text.delta":
                    delta = event.get("delta", "")
                    if delta:
                        self._current_text_buffer += delta
                        if USE_ELEVENLABS:
                            if not self._is_speaking:
                                await self._open_tts_stream()
                            if self.elevenlabs_ws:
                                try:
                                    await self.elevenlabs_ws.send(json.dumps({"text": delta}))
                                except Exception:
                                    pass

                # Text complete - flush TTS (ElevenLabs mode)
                elif event_type == "response.output_text.done":
                    text = event.get("text", "") or self._current_text_buffer
                    self._current_text_buffer = ""
                    if text:
                        logger.info(f"AI said: {text}")
                        await self._send_browser({"type": "transcript_ai", "text": text})
                    if USE_ELEVENLABS:
                        await self._flush_tts()

                # Audio transcript (native audio mode) - AI'nin söylediğinin text hali
                elif event_type == "response.audio_transcript.done" and not USE_ELEVENLABS:
                    text = event.get("transcript", "")
                    if text:
                        logger.info(f"AI said: {text}")
                        await self._send_browser({"type": "transcript_ai", "text": text})

                # Interrupt: user started speaking → kill TTS + clear browser
                elif event_type == "input_audio_buffer.speech_started":
                    logger.info("Speech detected, clearing audio")
                    if USE_ELEVENLABS:
                        await self._kill_tts()
                    await self._send_browser({"type": "clear_audio"})
                    self._current_text_buffer = ""

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    if transcript:
                        logger.info(f"User said: {transcript}")
                        await self._send_browser({"type": "transcript_user", "text": transcript})

                elif event_type == "response.function_call_arguments.done":
                    await self._handle_function_call(event)

                elif event_type == "error":
                    error_msg = event.get("error", {}).get("message", "Bilinmeyen hata")
                    logger.error(f"OpenAI error: {event.get('error', {})}")
                    await self._send_browser({"type": "error", "message": error_msg})

        except websockets.exceptions.ConnectionClosed:
            logger.info("OpenAI WebSocket closed")
        except Exception as e:
            logger.error(f"OpenAI listener error: {e}", exc_info=True)

    # ── ElevenLabs TTS ──────────────────────────────────────────────

    async def _open_tts_stream(self):
        await self._kill_tts()
        self._is_speaking = True

        try:
            url = _el_ws_url()
            logger.info(f"ElevenLabs opening stream (flash)")
            el_ws = await websockets.connect(url)
            self.elevenlabs_ws = el_ws

            await el_ws.send(json.dumps({
                "text": " ",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.85,
                },
                "xi_api_key": ELEVENLABS_API_KEY,
            }))

            self._tts_receiver_task = asyncio.create_task(self._tts_receiver(el_ws))
            logger.info("ElevenLabs stream opened")

        except Exception as e:
            logger.error(f"ElevenLabs open error: {e}", exc_info=True)
            self._is_speaking = False
            self.elevenlabs_ws = None

    async def _tts_receiver(self, el_ws):
        chunks = 0
        try:
            async for msg in el_ws:
                data = json.loads(msg)
                audio_b64 = data.get("audio")
                if audio_b64:
                    chunks += 1
                    await self._send_browser({"type": "audio", "audio": audio_b64})
                if data.get("isFinal"):
                    break
        except asyncio.CancelledError:
            pass
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"ElevenLabs receiver error: {e}", exc_info=True)
        finally:
            logger.info(f"ElevenLabs done: {chunks} chunks")
            self._is_speaking = False
            try:
                await el_ws.close()
            except Exception:
                pass
            self.elevenlabs_ws = None

    async def _flush_tts(self):
        if self.elevenlabs_ws:
            try:
                await self.elevenlabs_ws.send(json.dumps({"text": ""}))
            except Exception:
                pass

    async def _kill_tts(self):
        if self.elevenlabs_ws:
            try:
                await self.elevenlabs_ws.close()
            except Exception:
                pass
            self.elevenlabs_ws = None
        if self._tts_receiver_task and not self._tts_receiver_task.done():
            self._tts_receiver_task.cancel()
            self._tts_receiver_task = None
        self._is_speaking = False

    # ── Function calling ─────────────────────────────────────────────

    async def _handle_function_call(self, event):
        call_id = event.get("call_id", "")
        fn_name = event.get("name", "")
        args_str = event.get("arguments", "{}")

        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}

        logger.info(f"Function call: {fn_name}({args})")
        await self._send_browser({"type": "function_call", "name": fn_name, "args": args})

        result = await self._execute_function(fn_name, args)

        response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result, ensure_ascii=False),
            },
        }
        await self.openai_ws.send(json.dumps(response))
        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    async def _execute_function(self, fn_name: str, args: dict) -> dict:
        try:
            if fn_name == "list_packages":
                catalog = CatalogService(self.db)
                packages = catalog.list_packages(category=args.get("category"))
                return {"packages": packages}

            elif fn_name == "get_package":
                catalog = CatalogService(self.db)
                pkg = catalog.get_package(args["package_id"])
                return {"package": pkg} if pkg else {"error": "Paket bulunamadi"}

            elif fn_name == "validate_tckn":
                is_valid, error = validate_tckn(args["tckn"])
                if is_valid:
                    self.ctx.tckn = args["tckn"]
                else:
                    self.ctx.tckn_attempts += 1
                return {"valid": is_valid, "error": error}

            elif fn_name == "save_customer":
                return await self._save_customer(args)

            elif fn_name == "create_application":
                return await self._create_application()

            elif fn_name == "update_state":
                return await self._update_state(args)

            else:
                return {"error": f"Bilinmeyen fonksiyon: {fn_name}"}

        except Exception as e:
            logger.error(f"Function execution error: {e}", exc_info=True)
            return {"error": str(e)}

    async def _update_state(self, args: dict) -> dict:
        new_state_str = args.get("new_state", "")
        try:
            new_state = CallState(new_state_str)
            self.ctx.transition(new_state)
        except ValueError:
            return {"error": f"Gecersiz state: {new_state_str}"}

        for field in [
            "intent", "selected_package_id", "selected_team",
            "selected_payment_type", "name", "surname", "tckn",
            "birth_date", "phone", "city", "district", "neighborhood",
            "street", "building_no", "apartment_no",
        ]:
            if field in args and args[field]:
                setattr(self.ctx, field, args[field])

        if "selected_package_id" in args and args["selected_package_id"]:
            catalog = CatalogService(self.db)
            pkg = catalog.get_package(args["selected_package_id"])
            if pkg:
                self.ctx.selected_package_name = pkg["name"]
                self.ctx.selected_category = pkg["category"]
                self.ctx.selected_delivery = pkg["delivery"]

        if "phone" in args and args["phone"]:
            normalized, _ = normalize_phone(args["phone"])
            if normalized:
                self.ctx.phone = normalized

        await self._send_browser({"type": "state_change", "state": self.ctx.state.value})
        await self._update_session_prompt()

        return {"state": self.ctx.state.value, "summary": self.ctx.get_summary()}

    async def _update_session_prompt(self):
        if not self.openai_ws:
            return
        catalog_summary = self._get_catalog_summary()
        system_prompt = build_system_prompt(self.ctx, catalog_summary)
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {"type": "realtime", "instructions": system_prompt},
        }))

    async def _save_customer(self, args: dict) -> dict:
        is_valid, err = validate_tckn(args.get("tckn", ""))
        if not is_valid:
            return {"error": f"TCKN hatali: {err}"}

        phone = args.get("phone", "+905001234567")
        normalized_phone, err = normalize_phone(phone)
        if not normalized_phone:
            return {"error": f"Telefon hatali: {err}"}

        birth_date = None
        if args.get("birth_date"):
            parsed, err = parse_date(args["birth_date"])
            if not parsed:
                return {"error": f"Tarih hatali: {err}"}
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
        if not self.ctx.selected_package_id:
            return {"error": "Paket secilmedi"}

        catalog = CatalogService(self.db)
        pkg = catalog.get_package(self.ctx.selected_package_id)
        if not pkg:
            return {"error": "Paket bulunamadi"}

        customer_svc = CustomerService(self.db)
        customer = customer_svc.find_by_phone(self.ctx.phone or "+905001234567")
        if not customer:
            return {"error": "Musteri bulunamadi. Once save_customer cagirin."}

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

        return {
            "application_id": result["application_id"],
            "apply_url": result["apply_url"],
            "sms_sent": True,
        }

    def _get_catalog_summary(self) -> str:
        catalog = CatalogService(self.db)
        packages = catalog.list_packages()
        if not packages:
            return "Paket katalogu bos."
        lines = []
        for pkg in packages:
            prices = ", ".join(
                f"{p['payment_type']}: {p['amount_monthly']} {p['currency']}/ay"
                for p in pkg["pricing"]
            )
            team_info = f" (Takimlar: {', '.join(pkg['teams_supported'])})" if pkg["team_required"] else ""
            lines.append(f"- {pkg['name']} [{pkg['package_id']}]: {prices}{team_info}")
        return "\n".join(lines)

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
            if USE_ELEVENLABS:
                await self._kill_tts()
            if self.call_session:
                self.call_session.ended_at = datetime.now(timezone.utc)
                self.call_session.state_history = self.ctx.state_history
                self.call_session.flags = self.ctx.flags
                if self.ctx.state == CallState.CLOSE_FAIL:
                    self.call_session.status = "failed"
                elif self.ctx.state == CallState.CLOSE_SUCCESS:
                    self.call_session.status = "completed"
                self.call_session.conversation_summary = self.ctx.get_summary()
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to finalize call: {e}")
            self.db.rollback()
        finally:
            self.db.close()
