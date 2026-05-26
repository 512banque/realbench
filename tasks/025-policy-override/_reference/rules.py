from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    text: str
    effective_date: str
    conditions: tuple[str, ...] = ()
    overrides: tuple[str, ...] = ()


RULES = [
    Rule(
        "R-025-001",
        "Municipal Aerial Lane Day Operations",
        "Licensed drone carriers may operate in municipal aerial lanes for routine parcel delivery between 06:00 and 22:00.",
        "2027-01-01",
        ("C-025-licensed-carrier",),
    ),
    Rule(
        "R-025-004",
        "Calibration Module Cold-Chain Transport",
        "Calibration modules require a technical cold-chain endorsement and a filed technical handling manifest.",
        "2027-03-01",
        ("C-025-cold-chain-endorsement", "C-025-technical-manifest"),
    ),
    Rule(
        "R-025-006",
        "Night Drone Operation Prohibition",
        "Drone operation between 22:00 and 06:00 is prohibited unless a specific emergency utility override applies.",
        "2027-03-01",
    ),
    Rule(
        "R-025-009",
        "Emergency Utility Night Override",
        "Emergency-certified drone carriers may fly calibration modules at night for utility incidents, subject to R-025-004.",
        "2027-09-01",
        ("C-025-emergency-certification", "C-025-utility-incident"),
        ("R-025-006",),
    ),
]

EXPECTED_ANSWER = {
    "verdict": "ALLOWED",
    "applicable_rules": ["R-025-004", "R-025-009"],
    "overridden_rules": ["R-025-006"],
}
