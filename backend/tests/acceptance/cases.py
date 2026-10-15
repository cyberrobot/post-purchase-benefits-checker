"""Independent calendar expectations for the five pinned, narrow reference slices."""

from dataclasses import dataclass
from importlib import import_module


@dataclass(frozen=True)
class Case:
    brand: str
    model: str
    retailer: str
    purchase: str
    evaluation: str
    reward: str
    opens: str
    deadline: str
    expired_purchase: str
    expired_evaluation: str
    not_yet_open: str | None = None

    @property
    def helper(self):
        return import_module(f"tests.{self.brand.lower()}_reference")

    @property
    def manifest(self):
        return self.helper.reference_manifest()

    def arguments(self, **changes):
        return {
            "brand": self.brand,
            "model": self.model,
            "retailer": self.retailer,
            "purchase_date": self.purchase,
            **changes,
        }


CASES = (
    Case(
        "Samsung",
        "SM-R640",
        "Samsung.com",
        "2026-06-15",
        "2026-06-15",
        "50.00",
        "2026-06-15",
        "2026-07-14",
        "2026-06-23",
        "2026-07-23",
    ),
    Case(
        "LG",
        "OLED55G54LW.AEK",
        "LG.com/UK",
        "2025-06-24",
        "2025-08-19",
        "150.00",
        "2025-05-21",
        "2025-08-19",
        "2025-06-24",
        "2025-08-20",
    ),
    Case(
        "Hisense",
        "WF7I1248BBR",
        "Currys",
        "2026-09-09",
        "2026-11-27",
        "100.00",
        "2026-11-27",
        "2026-12-24",
        "2026-09-09",
        "2026-12-25",
        "2026-11-26",
    ),
    Case(
        "Hotpoint",
        "H7IC16M6 UK",
        "Wren",
        "2026-05-05",
        "2026-07-12",
        "75.00",
        "2026-06-04",
        "2026-12-04",
        "2026-05-05",
        "2026-12-05",
        "2026-06-03",
    ),
    Case(
        "Sony",
        "K55XR75M2B",
        "Currys - UK",
        "2026-09-30",
        "2026-12-02",
        "150.00",
        "2026-11-04",
        "2026-12-31",
        "2026-09-30",
        "2027-01-01",
        "2026-11-03",
    ),
)
