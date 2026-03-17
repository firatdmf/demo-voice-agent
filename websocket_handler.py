"""Twilio Media Streams <-> OpenAI Realtime API WebSocket bridge."""
import os
import json
import base64
import asyncio
import logging
from datetime import datetime, timezone

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from state_machine import CallContext, CallState
from prompts import build_system_prompt, OPENAI_TOOLS
from validators import validate_tckn, normalize_phone, parse_date
from db.database import SessionLocal
from db.models import CallSession, Package
from services.catalog_service import CatalogService
from services.customer_service import CustomerService
from services.application_service import ApplicationService
from services.sms_service import SMSService

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime-1.5"
VOICE = "shimmer"


class TwilioOpenAIBridge:
    """Bridges audio between Twilio Media Streams and OpenAI Realtime API."""

    def __init__(self, twilio_ws: WebSocket):
        self.twilio_ws = twilio_ws
        self.openai_ws = None
        self.stream_sid = None
        self.call_sid = None
        self.ctx = CallContext()
        self.db = SessionLocal()
        self.call_session = None

    async def handle(self):
        """Main handler - connects to OpenAI and bridges audio."""
        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            }
            async with websockets.connect(
                OPENAI_REALTIME_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            ) as openai_ws:
                self.openai_ws = openai_ws
                await self._configure_session()

                # Run both listeners concurrently
                await asyncio.gather(
                    self._listen_twilio(),
                    self._listen_openai(),
                )
        except Exception as e:
            logger.error(f"Bridge error: {e}", exc_info=True)
        finally:
            await self._finalize_call()

    async def _configure_session(self):
        """Configure OpenAI Realtime session."""
        catalog_summary = self._get_catalog_summary()
        system_prompt = build_system_prompt(self.ctx, catalog_summary)

        session_config = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": "gpt-realtime-1.5",
                "output_modalities": ["audio"],
                "instructions": system_prompt,
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcmu"},
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500
                        },
                        "transcription": {"model": "whisper-1"},
                    },
                    "output": {
                        "format": {"type": "audio/pcmu"},
                        "voice": VOICE,
                    },
                },
                "tools": OPENAI_TOOLS,
                "tool_choice": "auto",
            },
        }
        await self.openai_ws.send(json.dumps(session_config))
        logger.info("OpenAI session configured (Twilio mode, GA API, mulaw)")

    async def _listen_twilio(self):
        """Listen for messages from Twilio and forward audio to OpenAI."""
        try:
            while True:
                message = await self.twilio_ws.receive_text()
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    self.call_sid = data["start"].get("callSid", "")
                    self.ctx.call_sid = self.call_sid
                    self.ctx.caller_phone = data["start"].get("customParameters", {}).get("callerPhone", "")
                    logger.info(f"Twilio stream started: {self.stream_sid} (call: {self.call_sid})")
                    await self._create_call_session()

                elif event_type == "media":
                    payload = data["media"]["payload"]
                    audio_event = {
                        "type": "input_audio_buffer.append",
                        "audio": payload,
                    }
                    await self.openai_ws.send(json.dumps(audio_event))

                elif event_type == "stop":
                    logger.info("Twilio stream stopped")
                    break

        except WebSocketDisconnect:
            logger.info("Twilio WebSocket disconnected")
        except Exception as e:
            logger.error(f"Twilio listener error: {e}", exc_info=True)

    async def _listen_openai(self):
        """Listen for messages from OpenAI and forward audio/handle events."""
        try:
            async for message in self.openai_ws:
                event = json.loads(message)
                event_type = event.get("type", "")

                if event_type == "session.created":
                    logger.info("OpenAI session created")

                elif event_type == "session.updated":
                    logger.info("OpenAI session updated")

                elif event_type == "response.output_audio.delta":
                    # Forward audio to Twilio
                    audio_delta = event.get("delta", "")
                    if audio_delta:
                        twilio_msg = {
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": audio_delta},
                        }
                        await self.twilio_ws.send_json(twilio_msg)

                elif event_type == "response.output_audio_transcript.done":
                    transcript = event.get("transcript", "")
                    logger.info(f"AI said: {transcript}")

                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    logger.info(f"User said: {transcript}")

                elif event_type == "response.function_call_arguments.done":
                    await self._handle_function_call(event)

                elif event_type == "error":
                    logger.error(f"OpenAI error: {event.get('error', {})}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("OpenAI WebSocket closed")
        except Exception as e:
            logger.error(f"OpenAI listener error: {e}", exc_info=True)

    async def _handle_function_call(self, event):
        """Handle function calls from OpenAI."""
        call_id = event.get("call_id", "")
        fn_name = event.get("name", "")
        args_str = event.get("arguments", "{}")

        try:
            args = json.loads(args_str)
        except json.JSONDecodeError:
            args = {}

        logger.info(f"Function call: {fn_name}({args})")
        result = await self._execute_function(fn_name, args)

        # Send function result back to OpenAI
        response = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result, ensure_ascii=False),
            },
        }
        await self.openai_ws.send(json.dumps(response))

        # Trigger a new response after function call
        await self.openai_ws.send(json.dumps({"type": "response.create"}))

    async def _execute_function(self, fn_name: str, args: dict) -> dict:
        """Execute a function call and return the result."""
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
                return self._update_state(args)

            else:
                return {"error": f"Bilinmeyen fonksiyon: {fn_name}"}

        except Exception as e:
            logger.error(f"Function execution error: {e}", exc_info=True)
            return {"error": str(e)}

    def _update_state(self, args: dict) -> dict:
        """Update call context based on function call args."""
        new_state_str = args.get("new_state", "")
        try:
            new_state = CallState(new_state_str)
            self.ctx.transition(new_state)
        except ValueError:
            return {"error": f"Gecersiz state: {new_state_str}"}

        # Update context fields
        for field in [
            "intent", "selected_package_id", "selected_team",
            "selected_payment_type", "name", "surname", "tckn",
            "birth_date", "phone", "city", "district", "neighborhood",
            "street", "building_no", "apartment_no",
        ]:
            if field in args and args[field]:
                setattr(self.ctx, field, args[field])

        # If package selected, fetch its details
        if "selected_package_id" in args and args["selected_package_id"]:
            catalog = CatalogService(self.db)
            pkg = catalog.get_package(args["selected_package_id"])
            if pkg:
                self.ctx.selected_package_name = pkg["name"]
                self.ctx.selected_category = pkg["category"]
                self.ctx.selected_delivery = pkg["delivery"]

        # Normalize phone if provided
        if "phone" in args and args["phone"]:
            normalized, err = normalize_phone(args["phone"])
            if normalized:
                self.ctx.phone = normalized

        # Update system prompt
        asyncio.create_task(self._update_session_prompt())

        return {
            "state": self.ctx.state.value,
            "summary": self.ctx.get_summary(),
        }

    async def _update_session_prompt(self):
        """Update the OpenAI session with new system prompt."""
        if not self.openai_ws:
            return
        catalog_summary = self._get_catalog_summary()
        system_prompt = build_system_prompt(self.ctx, catalog_summary)
        update = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "instructions": system_prompt,
            },
        }
        await self.openai_ws.send(json.dumps(update))

    async def _save_customer(self, args: dict) -> dict:
        """Save customer to database."""
        # Validate TCKN
        is_valid, err = validate_tckn(args.get("tckn", ""))
        if not is_valid:
            return {"error": f"TCKN hatali: {err}"}

        # Normalize phone
        phone = args.get("phone", self.ctx.caller_phone)
        normalized_phone, err = normalize_phone(phone)
        if not normalized_phone:
            return {"error": f"Telefon hatali: {err}"}

        # Parse birth date
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

        # Update context
        self.ctx.phone = normalized_phone

        # Link to call session
        if self.call_session:
            self.call_session.customer_id = customer.id
            self.db.commit()

        return {
            "customer_id": str(customer.id),
            "status": "saved",
        }

    async def _create_application(self) -> dict:
        """Create application and send SMS."""
        if not self.ctx.selected_package_id:
            return {"error": "Paket secilmedi"}

        # Find package UUID
        catalog = CatalogService(self.db)
        pkg = catalog.get_package(self.ctx.selected_package_id)
        if not pkg:
            return {"error": "Paket bulunamadi"}

        # Get customer
        customer_svc = CustomerService(self.db)
        customer = customer_svc.find_by_phone(self.ctx.phone or self.ctx.caller_phone)
        if not customer:
            return {"error": "Musteri bulunamadi. Once save_customer cagirin."}

        # Create application
        app_svc = ApplicationService(self.db)
        result = app_svc.create_application(
            customer_id=customer.id,
            package_id=pkg["id"],
            payment_type=self.ctx.selected_payment_type or "credit_card_installment_12",
            delivery=self.ctx.selected_delivery or "kutusuz",
            team=self.ctx.selected_team,
        )

        # Send SMS
        sms_svc = SMSService(self.db)
        sms_svc.send_sms(
            application_id=result["application_id"],
            to_phone=self.ctx.phone or self.ctx.caller_phone,
            template="apply_link",
            params={"apply_url": result["apply_url"]},
        )

        self.db.commit()

        # Update context
        self.ctx.application_id = result["application_id"]
        self.ctx.apply_url = result["apply_url"]

        # Link to call session
        if self.call_session:
            self.call_session.application_id = result["application_id"]
            self.db.commit()

        return {
            "application_id": result["application_id"],
            "apply_url": result["apply_url"],
            "sms_sent": True,
        }

    def _get_catalog_summary(self) -> str:
        """Get a text summary of available packages for the system prompt."""
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
        """Create a call session record in the database."""
        try:
            self.call_session = CallSession(
                twilio_call_sid=self.call_sid,
                caller_phone=self.ctx.caller_phone,
                status="active",
            )
            self.db.add(self.call_session)
            self.db.commit()
            logger.info(f"Call session created: {self.call_session.id}")
        except Exception as e:
            logger.error(f"Failed to create call session: {e}")
            self.db.rollback()

    async def _finalize_call(self):
        """Finalize the call session."""
        try:
            if self.call_session:
                self.call_session.ended_at = datetime.now(timezone.utc)
                self.call_session.state_history = self.ctx.state_history
                self.call_session.flags = self.ctx.flags
                terminal = self.ctx.state in (CallState.CLOSE_SUCCESS, CallState.CLOSE_FAIL)
                if self.ctx.state == CallState.CLOSE_FAIL:
                    self.call_session.status = "failed"
                elif terminal:
                    self.call_session.status = "completed"
                self.call_session.conversation_summary = self.ctx.get_summary()
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to finalize call: {e}")
            self.db.rollback()
        finally:
            self.db.close()
