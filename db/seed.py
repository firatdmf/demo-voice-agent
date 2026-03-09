"""Seed script: loads 7 Digiturk packages into the database."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decimal import Decimal
from db.database import SessionLocal, engine, Base
from db.models import Package, PackagePricing

PACKAGES = [
    {
        "package_id": "FAN_UNBOXED",
        "name": "Taraftar Paketi (Kutusuz)",
        "category": "kampanyali_paketler",
        "delivery": "kutusuz",
        "platform": "beIN CONNECT",
        "team_required": True,
        "teams_supported": ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor"],
        "notes": ["beIN CONNECT ile aninda izleyin", "Kredi kartli odeme"],
        "pricing": [
            {"payment_type": "credit_card_installment_12", "amount_monthly": Decimal("449")},
        ],
    },
    {
        "package_id": "FAN_BOXED",
        "name": "Taraftar Paketi (Kutulu)",
        "category": "kutulu_paketler",
        "delivery": "kutulu",
        "platform": "kutu + kurulum",
        "team_required": True,
        "teams_supported": ["Galatasaray", "Fenerbahce", "Besiktas", "Trabzonspor"],
        "notes": ["beIN CONNECT ile aninda izleyin", "Faturali veya Kredi Kartli odeme"],
        "pricing": [
            {"payment_type": "credit_card_installment_12", "amount_monthly": Decimal("549")},
            {"payment_type": "invoiced", "amount_monthly": Decimal("669")},
        ],
    },
    {
        "package_id": "SPORTSTAR_UNBOXED",
        "name": "Sporun Yildizi (Kutusuz)",
        "category": "kampanyali_paketler",
        "delivery": "kutusuz",
        "platform": "beIN CONNECT",
        "team_required": False,
        "teams_supported": [],
        "notes": ["beIN CONNECT ile aninda izleyin", "Kredi kartli odeme"],
        "pricing": [
            {"payment_type": "credit_card_installment_12", "amount_monthly": Decimal("569")},
        ],
    },
    {
        "package_id": "SPORTSTAR_BOXED_PRIORITY_PROVINCES",
        "name": "Sporun Yildizi (Kutulu) - Kalkinmada Oncelikli Illere Ozel",
        "category": "kampanyali_paketler",
        "delivery": "kutulu",
        "platform": "kutu + kurulum",
        "team_required": False,
        "teams_supported": [],
        "notes": ["beIN CONNECT ile aninda izleyin", "Faturali veya Kredi Kartli odeme"],
        "pricing": [
            {"payment_type": "credit_card_installment_12", "amount_monthly": Decimal("549")},
            {"payment_type": "invoiced", "amount_monthly": Decimal("689")},
        ],
    },
    {
        "package_id": "NET_ENT_FAN_UNBOXED",
        "name": "Internet + Eglence + Taraftar (Kutusuz)",
        "category": "internet_paketleri",
        "delivery": "kutusuz",
        "platform": "Digiturk Internet + beIN CONNECT",
        "team_required": False,
        "teams_supported": [],
        "notes": ["Digiturk Internet ve beIN CONNECT bir arada", "6 ay tum kanallar hediye"],
        "pricing": [
            {"payment_type": "monthly", "amount_monthly": Decimal("599")},
        ],
    },
    {
        "package_id": "NET_ENT_FAN_BOXED",
        "name": "Internet + Eglence + Taraftar (Kutulu)",
        "category": "internet_paketleri",
        "delivery": "kutulu",
        "platform": "Digiturk Internet + kutu + kurulum",
        "team_required": False,
        "teams_supported": [],
        "notes": ["Limitsiz internet, Film, Dizi, Avrupa Ligleri", "12 ay taraftar paketi hediye"],
        "pricing": [
            {"payment_type": "monthly", "amount_monthly": Decimal("659")},
        ],
    },
    {
        "package_id": "NET_ENT_SPORTSTAR_UNBOXED",
        "name": "Internet + Eglence + Sporun Yildizi (Kutusuz)",
        "category": "internet_paketleri",
        "delivery": "kutusuz",
        "platform": "Digiturk Internet + beIN CONNECT",
        "team_required": False,
        "teams_supported": [],
        "notes": ["Limitsiz internet, Film, Dizi, Avrupa Ligleri", "12 ay taraftar paketi hediye"],
        "pricing": [
            {"payment_type": "monthly", "amount_monthly": Decimal("999")},
        ],
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for pkg_data in PACKAGES:
            existing = db.query(Package).filter(Package.package_id == pkg_data["package_id"]).first()
            if existing:
                print(f"  Skipping {pkg_data['package_id']} (already exists)")
                continue

            pricing_data = pkg_data.pop("pricing")
            pkg = Package(**pkg_data)
            db.add(pkg)
            db.flush()

            for price in pricing_data:
                pp = PackagePricing(package_id=pkg.id, **price)
                db.add(pp)

            print(f"  Added {pkg_data['package_id']}")

        db.commit()
        print("Seed completed successfully.")
    except Exception as e:
        db.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
