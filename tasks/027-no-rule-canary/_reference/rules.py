from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    effective_date: str
    scope_note: str
    conditions: tuple[str, ...] = ()


RULES = [
    Rule("R-027-002", "Municipal Aerial Drone Deliveries", "2027-01-01", "aerial drones", ("C-027-aerial-drone-license",)),
    Rule("R-027-006", "Warehouse Forklift Movements", "2027-01-01", "warehouse perimeter", ("C-027-warehouse-perimeter",)),
    Rule("R-027-010", "Commercial Blue-Zone Delivery Robots", "2027-05-01", "commercial blue zones", ("C-027-blue-zone-robot-permit",)),
    Rule("R-027-013", "Campus Food Carts", "2027-05-01", "university campus routes", ("C-027-campus-vendor-permit",)),
    Rule("R-027-018", "Technical Sample Ground Carts", "2027-07-01", "technical samples in utility districts", ("C-027-technical-cart-endorsement",)),
    Rule("R-027-022", "Municipal Waste Bots", "2027-07-01", "municipal waste collection", ("C-027-waste-route-assignment",)),
    Rule("R-027-025", "Security Patrol Rovers", "2027-09-01", "security patrol assignment", ("C-027-security-patrol-assignment",)),
    Rule("R-027-030", "Controlled Chemical Movement", "2027-10-01", "controlled chemical movement", ("C-027-chemical-movement-permit",)),
]

EXPECTED_ANSWER = {
    "verdict": "NO_RULE",
    "applicable_rules": [],
    "overridden_rules": [],
}
