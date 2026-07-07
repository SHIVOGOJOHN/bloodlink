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
        name="Blood Hero",
        threshold=10,
        points=200,
        description="Ten confirmed donations — you are a trusted lifesaver.",
        icon_svg="""
<svg width=\"16\" height=\"16\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M20 6.5v6.3a8 8 0 0 1-5.6 7.6L12 22l-2.4-1.6A8 8 0 0 1 4 12.8V6.5\"/><path d=\"M12 10.5v6\"/><path d=\"M9.5 13.5h5\"/></svg>
""",
        color="#f59e0b",
    ),
]


def get_badges_for_donation_count(donation_count: int) -> List[BadgeDefinition]:
    return [badge for badge in BADGE_DEFINITIONS if donation_count >= badge.threshold]


def get_next_badge(donation_count: int) -> Optional[BadgeDefinition]:
    for badge in BADGE_DEFINITIONS:
        if donation_count < badge.threshold:
            return badge
    return None


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
