from sqlalchemy.orm import Session, joinedload
from db.models import Package, PackagePricing
from typing import Optional, List, Dict


class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def list_packages(self, category: Optional[str] = None, active_only: bool = True) -> List[dict]:
        q = self.db.query(Package).options(joinedload(Package.pricing))
        if active_only:
            q = q.filter(Package.is_active == True)
        if category:
            q = q.filter(Package.category == category)
        packages = q.all()
        return [self._to_dict(p) for p in packages]

    def get_package(self, package_id: str) -> Optional[dict]:
        pkg = (
            self.db.query(Package)
            .options(joinedload(Package.pricing))
            .filter(Package.package_id == package_id, Package.is_active == True)
            .first()
        )
        return self._to_dict(pkg) if pkg else None

    def get_package_by_uuid(self, uuid) -> Optional[dict]:
        pkg = (
            self.db.query(Package)
            .options(joinedload(Package.pricing))
            .filter(Package.id == uuid)
            .first()
        )
        return self._to_dict(pkg) if pkg else None

    def _to_dict(self, pkg: Package) -> dict:
        return {
            "id": str(pkg.id),
            "package_id": pkg.package_id,
            "name": pkg.name,
            "category": pkg.category,
            "delivery": pkg.delivery,
            "platform": pkg.platform,
            "team_required": pkg.team_required,
            "teams_supported": pkg.teams_supported or [],
            "notes": pkg.notes or [],
            "pricing": [
                {
                    "payment_type": p.payment_type,
                    "amount_monthly": float(p.amount_monthly),
                    "currency": p.currency,
                }
                for p in pkg.pricing
            ],
        }
