from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BadgeDefinition:
    name: str
    threshold: int
    points: int
    description: str
    icon_svg: str
    color: str


@dataclass
class CertificateDefinition:
    title: str
    description: str
    icon_svg: str
    color: str


BADGE_DEFINITIONS: List[BadgeDefinition] = [
    BadgeDefinition(
        name="First Drop",
        threshold=1,
        points=50,
        description="Confirmed your first blood donation.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 22s8-4.5 8-11a8 8 0 0 0-16 0c0 6.5 8 11 8 11z\"/><path d=\"M12 6.5v5\"/></svg>
""",
        color="#e63946",
    ),
    BadgeDefinition(
        name="Blood Ally",
        threshold=3,
        points=75,
        description="Three confirmed donations and growing your lifesaving streak.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 20c4.418 0 8-3.582 8-8s-3.582-8-8-8-8 3.582-8 8 3.582 8 8 8Z\"/><path d=\"M8 12h8\"/><path d=\"M12 8v8\"/></svg>
""",
        color="#2563eb",
    ),
    BadgeDefinition(
        name="Life Saver",
        threshold=5,
        points=100,
        description="Five confirmed donations and rising to save more lives.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M20.8 4.6a5.7 5.7 0 0 0-8.1 0l-.7.7-.7-.7a5.7 5.7 0 1 0-8.1 8.1l9.1 9.1 9.1-9.1a5.7 5.7 0 0 0 0-8.1Z\"/></svg>
""",
        color="#1e7e34",
    ),
    BadgeDefinition(
        name="Rare Blood Hero",
        threshold=10,
        points=150,
        description="Ten confirmed donations and a rare blood champion.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 2l2.5 7.7H22l-6.3 4.6 2.4 7.7L12 17.5 6 22.0l2.4-7.7L2 9.7h7.5L12 2Z\"/></svg>
""",
        color="#8b5cf6",
    ),
    BadgeDefinition(
        name="Emergency Responder",
        threshold=15,
        points=200,
        description="Fifteen confirmed donations and ready for urgent missions.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z\"/><path d=\"M15 9h-2V7h-2v2H9v2h2v2h2v-2h2V9Z\"/></svg>
""",
        color="#dc2626",
    ),
]


def get_badges_for_donation_count(donation_count: int) -> List[BadgeDefinition]:
    return [badge for badge in BADGE_DEFINITIONS if donation_count >= badge.threshold]


def get_next_badge(donation_count: int) -> Optional[BadgeDefinition]:
    for badge in BADGE_DEFINITIONS:
        if donation_count < badge.threshold:
            return badge
    return None


def get_badge_progress(donation_count: int) -> dict[str, Optional[int] | str]:
    next_badge = get_next_badge(donation_count)
    if not next_badge:
        return {
            "next_badge": None,
            "progress": 100,
            "needed": 0,
            "target": donation_count,
        }

    previous_threshold = 0
    for badge in BADGE_DEFINITIONS:
        if badge.threshold >= next_badge.threshold:
            break
        previous_threshold = badge.threshold

    total_span = next_badge.threshold - previous_threshold
    progress = int((donation_count - previous_threshold) / total_span * 100) if total_span > 0 else 100
    return {
        "next_badge": next_badge,
        "progress": max(0, min(100, progress)),
        "needed": max(0, next_badge.threshold - donation_count),
        "target": next_badge.threshold,
    }


def get_certificates_for_donation_count(donation_count: int, blood_type: str) -> List[CertificateDefinition]:
    certificates: List[CertificateDefinition] = []
    if donation_count >= 1:
        certificates.append(CertificateDefinition(
            title="First Donation Certificate",
            description="Recognizes your first confirmed blood donation.",
            icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 2l3.5 7.5H22l-6 4.5 2.5 8-6-4.5-6 4.5L8 14 2 9.5h6.5L12 2Z\"/></svg>
""",
            color="#2563eb",
        ))
    if donation_count >= 5:
        certificates.append(CertificateDefinition(
            title="Responder Certificate",
            description="Honors your commitment to helping urgent cases.",
            icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M7 7h10M12 3v18M4 12h16\"/></svg>
""",
            color="#16a34a",
        ))
    if blood_type == "O-" and donation_count >= 3:
        certificates.append(CertificateDefinition(
            title="Rare Blood Hero",
            description="Acknowledge your rare type donations and high impact.",
            icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 21c4.97 0 9-4.03 9-9S16.97 3 12 3 3 7.03 3 12s4.03 9 9 9Z\"/><path d=\"M9.5 12.5 11 14l3.5-3.5\"/></svg>
""",
            color="#7c3aed",
        ))
    return certificates


def get_rank_for_points(points: int) -> str:
    if points >= 300:
        return "Blood Shield"
    if points >= 150:
        return "Lifesaver"
    if points >= 50:
        return "Community Ally"
    return "Novice Donor"


def calculate_reward_for_donation(previous_confirmed_count: int) -> tuple[int, List[str]]:
    """Return loyalty points and any newly unlocked badge names for this new confirmed donation."""
    new_count = previous_confirmed_count + 1
    points = 25
    unlocked: List[str] = []

    for badge in BADGE_DEFINITIONS:
        if badge.threshold == new_count:
            points += badge.points
            unlocked.append(badge.name)

    return points, unlocked
