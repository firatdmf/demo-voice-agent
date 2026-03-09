"""State machine for Digiturk sales call flow."""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class CallState(str, Enum):
    GREET = "GREET"
    INTENT = "INTENT"
    PACKAGE_DISCOVERY = "PACKAGE_DISCOVERY"
    INTERNET_PACKAGE_DISCOVERY = "INTERNET_PACKAGE_DISCOVERY"
    PACKAGE_RECOMMEND = "PACKAGE_RECOMMEND"
    CONFIRM_CHOICE = "CONFIRM_CHOICE"
    COLLECT_IDENTITY = "COLLECT_IDENTITY"
    COLLECT_ADDRESS_IF_NEEDED = "COLLECT_ADDRESS_IF_NEEDED"
    COLLECT_ADDRESS = "COLLECT_ADDRESS"
    VERIFY_SUMMARY = "VERIFY_SUMMARY"
    CORRECT_DATA = "CORRECT_DATA"
    CREATE_LINK = "CREATE_LINK"
    GUIDE_SMS = "GUIDE_SMS"
    OFFTOPIC_POLICY = "OFFTOPIC_POLICY"
    ABUSE_POLICY = "ABUSE_POLICY"
    CLOSE_SUCCESS = "CLOSE_SUCCESS"
    CLOSE_FAIL = "CLOSE_FAIL"


@dataclass
class CallContext:
    """Holds all collected data during a call."""
    call_sid: str = ""
    caller_phone: str = ""
    state: CallState = CallState.GREET
    state_history: list = field(default_factory=list)

    # Intent
    intent: Optional[str] = None  # sales, internet_sales, offtopic

    # Package selection
    selected_package_id: Optional[str] = None
    selected_package_name: Optional[str] = None
    selected_category: Optional[str] = None
    selected_delivery: Optional[str] = None
    selected_team: Optional[str] = None
    selected_payment_type: Optional[str] = None

    # Customer identity slots
    name: Optional[str] = None
    surname: Optional[str] = None
    tckn: Optional[str] = None
    birth_date: Optional[str] = None
    phone: Optional[str] = None

    # Address slots
    city: Optional[str] = None
    district: Optional[str] = None
    neighborhood: Optional[str] = None
    street: Optional[str] = None
    building_no: Optional[str] = None
    apartment_no: Optional[str] = None
    address_freeform: Optional[str] = None

    # Application
    application_id: Optional[str] = None
    apply_url: Optional[str] = None

    # Counters
    offtopic_warnings: int = 0
    abuse_warnings: int = 0
    low_confidence_streak: int = 0
    tckn_attempts: int = 0

    # Flags
    flags: list = field(default_factory=list)

    def transition(self, new_state: CallState):
        self.state_history.append({
            "from": self.state.value,
            "to": new_state.value,
        })
        self.state = new_state

    def get_filled_identity_slots(self) -> dict:
        slots = {}
        for key in ["name", "surname", "tckn", "birth_date", "phone"]:
            val = getattr(self, key)
            if val:
                slots[key] = val
        return slots

    def get_filled_address_slots(self) -> dict:
        slots = {}
        for key in ["city", "district", "neighborhood", "street", "building_no", "apartment_no"]:
            val = getattr(self, key)
            if val:
                slots[key] = val
        return slots

    def needs_address(self) -> bool:
        return self.selected_category == "internet_paketleri" or self.selected_delivery == "kutulu"

    def identity_complete(self) -> bool:
        return all([self.name, self.surname, self.tckn, self.birth_date, self.phone])

    def address_complete(self) -> bool:
        return all([self.city, self.district, self.neighborhood])

    def get_summary(self) -> str:
        parts = []
        if self.selected_package_name:
            parts.append(f"Paket: {self.selected_package_name}")
        if self.selected_team:
            parts.append(f"Takim: {self.selected_team}")
        if self.selected_delivery:
            delivery_tr = "Kutusuz" if self.selected_delivery == "kutusuz" else "Kutulu"
            parts.append(f"Teslimat: {delivery_tr}")
        if self.selected_payment_type:
            pt_map = {
                "credit_card_installment_12": "Kredi Karti 12 Taksit",
                "invoiced": "Faturali",
                "monthly": "Aylik Odeme",
            }
            parts.append(f"Odeme: {pt_map.get(self.selected_payment_type, self.selected_payment_type)}")
        if self.name and self.surname:
            parts.append(f"Ad Soyad: {self.name} {self.surname}")
        if self.tckn:
            parts.append(f"TCKN: ***{self.tckn[-4:]}")
        if self.birth_date:
            parts.append(f"Dogum Tarihi: {self.birth_date}")
        if self.phone:
            parts.append(f"Telefon: {self.phone}")
        if self.city:
            addr_parts = [self.city]
            if self.district:
                addr_parts.append(self.district)
            if self.neighborhood:
                addr_parts.append(self.neighborhood)
            parts.append(f"Adres: {', '.join(addr_parts)}")
        return "; ".join(parts)
