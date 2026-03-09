import hashlib
from datetime import date
from sqlalchemy.orm import Session
from db.models import Customer
from typing import Optional


class CustomerService:
    def __init__(self, db: Session):
        self.db = db

    def create_customer(
        self,
        name: str,
        surname: str,
        phone: str,
        tckn: Optional[str] = None,
        birth_date: Optional[date] = None,
        city: Optional[str] = None,
        district: Optional[str] = None,
        neighborhood: Optional[str] = None,
        street: Optional[str] = None,
        building_no: Optional[str] = None,
        apartment_no: Optional[str] = None,
        address_freeform: Optional[str] = None,
    ) -> Customer:
        tckn_hash = self._hash_tckn(tckn) if tckn else None
        customer = Customer(
            name=name,
            surname=surname,
            tckn=tckn_hash,
            birth_date=birth_date,
            phone=phone,
            city=city,
            district=district,
            neighborhood=neighborhood,
            street=street,
            building_no=building_no,
            apartment_no=apartment_no,
            address_freeform=address_freeform,
        )
        self.db.add(customer)
        self.db.flush()
        return customer

    def find_by_phone(self, phone: str) -> Optional[Customer]:
        return self.db.query(Customer).filter(Customer.phone == phone).first()

    def update_customer(self, customer_id, **kwargs) -> Optional[Customer]:
        customer = self.db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None
        if "tckn" in kwargs and kwargs["tckn"]:
            kwargs["tckn"] = self._hash_tckn(kwargs["tckn"])
        for key, value in kwargs.items():
            if value is not None:
                setattr(customer, key, value)
        self.db.flush()
        return customer

    @staticmethod
    def _hash_tckn(tckn: str) -> str:
        return hashlib.sha256(tckn.encode()).hexdigest()
