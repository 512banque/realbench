from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    effective_date: str
    conditions: tuple[str, ...] = ()
    overrides: tuple[str, ...] = ()


RULES = [
    Rule(
        "R-026-001",
        "Campus Wallet Exemption",
        "2026-01-01",
        ("C-026-campus-wallet-low-volume",),
    ),
    Rule(
        "R-026-005",
        "PSP-Lite Registration Requirement",
        "2027-07-01",
        ("C-026-psp-lite-registration",),
        ("R-026-001",),
    ),
    Rule(
        "R-026-008",
        "Existing Operator Transition Period",
        "2027-07-01",
        ("C-026-transition-filing",),
    ),
]

EXPECTED_ANSWER = {
    "verdict": "PROHIBITED",
    "applicable_rules": ["R-026-005", "R-026-008"],
    "overridden_rules": ["R-026-001"],
}
