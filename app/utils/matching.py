"""
matching.py — Explainable Matching Engine for BloodLink.

Algorithm (fully transparent, no black-box logic):
  1. COMPATIBILITY  — blood type compatibility using standard transfusion rules.
                      O- is universal donor; AB+ is universal recipient, etc.
  2. ELIGIBILITY    — last donation date must be >= 90 days ago (WHO guideline).
  3. PROXIMITY      — static county-distance lookup (approximate road km).
                      Same county = 10 pts, <= 25 km = 7 pts, <= 80 km = 5 pts,
                      <= 200 km = 2 pts, > 200 km = 0 pts.

Total score is out of 100:
  Compatibility  60 pts
  Eligibility    30 pts
  Proximity      10 pts

AI (Groq → Gemini → baseline) generates a short, human-readable explanation
for each matched donor so judges can see exactly why each person ranked where
they did.
"""

import logging
import math
from datetime import date
from typing import Any

from app.models import Donor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Standard blood-type compatibility
#    Key   = blood type a donor CAN DONATE TO (recipient types)
#    Value = set of recipient blood types that can receive from this donor
# ---------------------------------------------------------------------------

# Maps donor blood type → set of recipient blood types they can donate to
DONOR_TO_RECIPIENTS: dict[str, set[str]] = {
    "O-":  {"O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"},   # universal donor
    "O+":  {"O+", "A+", "B+", "AB+"},
    "A-":  {"A-", "A+", "AB-", "AB+"},
    "A+":  {"A+", "AB+"},
    "B-":  {"B-", "B+", "AB-", "AB+"},
    "B+":  {"B+", "AB+"},
    "AB-": {"AB-", "AB+"},
    "AB+": {"AB+"},                                                 # universal recipient (donor)
}


def is_compatible(donor_blood_type: str, recipient_blood_type: str) -> bool:
    """Return True if donor_blood_type can donate to recipient_blood_type."""
    return recipient_blood_type in DONOR_TO_RECIPIENTS.get(donor_blood_type, set())


# ---------------------------------------------------------------------------
# 2. 90-day eligibility rule
# ---------------------------------------------------------------------------

ELIGIBILITY_DAYS = 90


def is_eligible(donor: "Donor", reference_date: date | None = None) -> tuple[bool, int | None]:
    """
    Returns (eligible: bool, days_since_last: int | None).
    Donors with no recorded last_donation_date are considered eligible.
    """
    ref = reference_date or date.today()
    if not donor.last_donation_date:
        return True, None
    days = (ref - donor.last_donation_date).days
    return days >= ELIGIBILITY_DAYS, days


# ---------------------------------------------------------------------------
# 3. Static county-distance lookup (approximate road km between county centres)


COUNTY_DISTANCE: dict[str, dict[str, int]] = {
    'Baringo': {
        'Baringo': 0, 'Bomet': 209, 'Bungoma': 212, 'Busia': 278,
        'Elgeyo Marakwet': 81, 'Embu': 270, 'Garissa': 570, 'Homa Bay': 271,
        'Isiolo': 243, 'Kajiado': 369, 'Kakamega': 185, 'Kericho': 162,
        'Kiambu': 279, 'Kilifi': 841, 'Kirinyaga': 244, 'Kisii': 247,
        'Kisumu': 198, 'Kitui': 413, 'Kwale': 871, 'Laikipia': 131,
        'Lamu': 846, 'Machakos': 356, 'Makueni': 421, 'Mandera': 1025,
        'Marsabit': 413, 'Meru': 265, 'Migori': 321, 'Mombasa': 876,
        'Muranga': 251, 'Nairobi': 293, 'Nakuru': 117, 'Nandi': 135,
        'Narok': 232, 'Nyamira': 220, 'Nyandarua': 159, 'Nyeri': 198,
        'Samburu': 180, 'Siaya': 265, 'Taita Taveta': 682, 'Tana River': 675,
        'Tharaka Nithi': 302, 'Trans Nzoia': 166, 'Turkana': 402, 'Uasin Gishu': 105,
        'Vihiga': 196, 'Wajir': 644, 'West Pokot': 173,
    },
    'Bomet': {
        'Baringo': 209, 'Bomet': 0, 'Bungoma': 235, 'Busia': 263,
        'Elgeyo Marakwet': 234, 'Embu': 319, 'Garissa': 647, 'Homa Bay': 139,
        'Isiolo': 377, 'Kajiado': 269, 'Kakamega': 184, 'Kericho': 63,
        'Kiambu': 231, 'Kilifi': 796, 'Kirinyaga': 293, 'Kisii': 86,
        'Kisumu': 136, 'Kitui': 409, 'Kwale': 798, 'Laikipia': 263,
        'Lamu': 863, 'Machakos': 308, 'Makueni': 373, 'Mandera': 1206,
        'Marsabit': 613, 'Meru': 362, 'Migori': 138, 'Mombasa': 811,
        'Muranga': 270, 'Nairobi': 234, 'Nakuru': 131, 'Nandi': 150,
        'Narok': 90, 'Nyamira': 70, 'Nyandarua': 197, 'Nyeri': 247,
        'Samburu': 374, 'Siaya': 193, 'Taita Taveta': 598, 'Tana River': 709,
        'Tharaka Nithi': 392, 'Trans Nzoia': 275, 'Turkana': 587, 'Uasin Gishu': 196,
        'Vihiga': 159, 'Wajir': 802, 'West Pokot': 305,
    },
    'Bungoma': {
        'Baringo': 212, 'Bomet': 235, 'Bungoma': 0, 'Busia': 69,
        'Elgeyo Marakwet': 147, 'Embu': 464, 'Garissa': 779, 'Homa Bay': 165,
        'Isiolo': 455, 'Kajiado': 493, 'Kakamega': 51, 'Kericho': 177,
        'Kiambu': 429, 'Kilifi': 1008, 'Kirinyaga': 437, 'Kisii': 189,
        'Kisumu': 103, 'Kitui': 594, 'Kwale': 1022, 'Laikipia': 340,
        'Lamu': 1042, 'Machakos': 512, 'Makueni': 580, 'Mandera': 1204,
        'Marsabit': 579, 'Meru': 473, 'Migori': 244, 'Mombasa': 1033,
        'Muranga': 433, 'Nairobi': 439, 'Nakuru': 262, 'Nandi': 101,
        'Narok': 316, 'Nyamira': 178, 'Nyandarua': 338, 'Nyeri': 387,
        'Samburu': 374, 'Siaya': 103, 'Taita Taveta': 824, 'Tana River': 875,
        'Tharaka Nithi': 510, 'Trans Nzoia': 96, 'Turkana': 413, 'Uasin Gishu': 107,
        'Vihiga': 77, 'Wajir': 844, 'West Pokot': 131,
    },
    'Busia': {
        'Baringo': 278, 'Bomet': 263, 'Bungoma': 69, 'Busia': 0,
        'Elgeyo Marakwet': 216, 'Embu': 524, 'Garissa': 842, 'Homa Bay': 157,
        'Isiolo': 521, 'Kajiado': 531, 'Kakamega': 100, 'Kericho': 216,
        'Kiambu': 477, 'Kilifi': 1054, 'Kirinyaga': 497, 'Kisii': 198,
        'Kisumu': 128, 'Kitui': 647, 'Kwale': 1061, 'Laikipia': 405,
        'Lamu': 1099, 'Machakos': 559, 'Makueni': 626, 'Mandera': 1272,
        'Marsabit': 647, 'Meru': 536, 'Migori': 235, 'Mombasa': 1073,
        'Muranga': 489, 'Nairobi': 485, 'Nakuru': 317, 'Nandi': 157,
        'Narok': 351, 'Nyamira': 197, 'Nyandarua': 394, 'Nyeri': 446,
        'Samburu': 443, 'Siaya': 82, 'Taita Taveta': 861, 'Tana River': 933,
        'Tharaka Nithi': 574, 'Trans Nzoia': 158, 'Turkana': 456, 'Uasin Gishu': 174,
        'Vihiga': 108, 'Wajir': 913, 'West Pokot': 190,
    },
    'Elgeyo Marakwet': {
        'Baringo': 81, 'Bomet': 234, 'Bungoma': 147, 'Busia': 216,
        'Elgeyo Marakwet': 0, 'Embu': 351, 'Garissa': 647, 'Homa Bay': 251,
        'Isiolo': 316, 'Kajiado': 436, 'Kakamega': 136, 'Kericho': 174,
        'Kiambu': 352, 'Kilifi': 921, 'Kirinyaga': 325, 'Kisii': 243,
        'Kisumu': 171, 'Kitui': 493, 'Kwale': 948, 'Laikipia': 211,
        'Lamu': 927, 'Machakos': 432, 'Makueni': 498, 'Mandera': 1062,
        'Marsabit': 439, 'Meru': 343, 'Migori': 316, 'Mombasa': 953,
        'Muranga': 331, 'Nairobi': 366, 'Nakuru': 181, 'Nandi': 107,
        'Narok': 282, 'Nyamira': 219, 'Nyandarua': 238, 'Nyeri': 279,
        'Samburu': 227, 'Siaya': 223, 'Taita Taveta': 756, 'Tana River': 755,
        'Tharaka Nithi': 382, 'Trans Nzoia': 85, 'Turkana': 352, 'Uasin Gishu': 53,
        'Vihiga': 158, 'Wajir': 697, 'West Pokot': 93,
    },
    'Embu': {
        'Baringo': 270, 'Bomet': 319, 'Bungoma': 464, 'Busia': 524,
        'Elgeyo Marakwet': 351, 'Embu': 0, 'Garissa': 329, 'Homa Bay': 451,
        'Isiolo': 135, 'Kajiado': 223, 'Kakamega': 424, 'Kericho': 327,
        'Kiambu': 135, 'Kilifi': 579, 'Kirinyaga': 27, 'Kisii': 402,
        'Kisumu': 409, 'Kitui': 151, 'Kwale': 622, 'Laikipia': 147,
        'Lamu': 579, 'Machakos': 151, 'Makueni': 192, 'Mandera': 940,
        'Marsabit': 437, 'Meru': 78, 'Migori': 455, 'Mombasa': 622,
        'Muranga': 54, 'Nairobi': 148, 'Nakuru': 209, 'Nandi': 367,
        'Narok': 252, 'Nyamira': 379, 'Nyandarua': 131, 'Nyeri': 78,
        'Samburu': 251, 'Siaya': 481, 'Taita Taveta': 451, 'Tana River': 409,
        'Tharaka Nithi': 84, 'Trans Nzoia': 436, 'Turkana': 614, 'Uasin Gishu': 364,
        'Vihiga': 421, 'Wajir': 520, 'West Pokot': 441,
    },
    'Garissa': {
        'Baringo': 570, 'Bomet': 647, 'Bungoma': 779, 'Busia': 842,
        'Elgeyo Marakwet': 647, 'Embu': 329, 'Garissa': 0, 'Homa Bay': 779,
        'Isiolo': 333, 'Kajiado': 478, 'Kakamega': 744, 'Kericho': 655,
        'Kiambu': 436, 'Kilifi': 460, 'Kirinyaga': 355, 'Kisii': 732,
        'Kisumu': 734, 'Kitui': 281, 'Kwale': 559, 'Laikipia': 439,
        'Lamu': 331, 'Machakos': 392, 'Makueni': 366, 'Mandera': 737,
        'Marsabit': 487, 'Meru': 306, 'Migori': 782, 'Mombasa': 539,
        'Muranga': 377, 'Nairobi': 443, 'Nakuru': 536, 'Nandi': 687,
        'Narok': 574, 'Nyamira': 707, 'Nyandarua': 458, 'Nyeri': 405,
        'Samburu': 459, 'Siaya': 807, 'Taita Taveta': 482, 'Tana River': 163,
        'Tharaka Nithi': 269, 'Trans Nzoia': 732, 'Turkana': 811, 'Uasin Gishu': 674,
        'Vihiga': 744, 'Wajir': 338, 'West Pokot': 726,
    },
    'Homa Bay': {
        'Baringo': 271, 'Bomet': 139, 'Bungoma': 165, 'Busia': 157,
        'Elgeyo Marakwet': 251, 'Embu': 451, 'Garissa': 779, 'Homa Bay': 0,
        'Isiolo': 487, 'Kajiado': 402, 'Kakamega': 130, 'Kericho': 127,
        'Kiambu': 370, 'Kilifi': 933, 'Kirinyaga': 424, 'Kisii': 54,
        'Kisumu': 80, 'Kitui': 549, 'Kwale': 927, 'Laikipia': 369,
        'Lamu': 1002, 'Machakos': 447, 'Makueni': 512, 'Mandera': 1296,
        'Marsabit': 682, 'Meru': 485, 'Migori': 81, 'Mombasa': 944,
        'Muranga': 405, 'Nairobi': 373, 'Nakuru': 246, 'Nandi': 146,
        'Narok': 228, 'Nyamira': 72, 'Nyandarua': 323, 'Nyeri': 374,
        'Samburu': 451, 'Siaya': 74, 'Taita Taveta': 726, 'Tana River': 846,
        'Tharaka Nithi': 517, 'Trans Nzoia': 246, 'Turkana': 572, 'Uasin Gishu': 198,
        'Vihiga': 99, 'Wajir': 907, 'West Pokot': 282,
    },
    'Isiolo': {
        'Baringo': 243, 'Bomet': 377, 'Bungoma': 455, 'Busia': 521,
        'Elgeyo Marakwet': 316, 'Embu': 135, 'Garissa': 333, 'Homa Bay': 487,
        'Isiolo': 0, 'Kajiado': 352, 'Kakamega': 425, 'Kericho': 362,
        'Kiambu': 255, 'Kilifi': 678, 'Kirinyaga': 135, 'Kisii': 448,
        'Kisumu': 428, 'Kitui': 266, 'Kwale': 736, 'Laikipia': 120,
        'Lamu': 636, 'Machakos': 285, 'Makueni': 324, 'Mandera': 836,
        'Marsabit': 302, 'Meru': 61, 'Migori': 513, 'Mombasa': 730,
        'Muranga': 174, 'Nairobi': 273, 'Nakuru': 246, 'Nandi': 371,
        'Narok': 335, 'Nyamira': 421, 'Nyandarua': 185, 'Nyeri': 150,
        'Samburu': 139, 'Siaya': 498, 'Taita Taveta': 575, 'Tana River': 458,
        'Tharaka Nithi': 90, 'Trans Nzoia': 400, 'Turkana': 510, 'Uasin Gishu': 348,
        'Vihiga': 431, 'Wajir': 427, 'West Pokot': 394,
    },
    'Kajiado': {
        'Baringo': 369, 'Bomet': 269, 'Bungoma': 493, 'Busia': 531,
        'Elgeyo Marakwet': 436, 'Embu': 223, 'Garissa': 478, 'Homa Bay': 402,
        'Isiolo': 352, 'Kajiado': 0, 'Kakamega': 443, 'Kericho': 316,
        'Kiambu': 101, 'Kilifi': 531, 'Kirinyaga': 217, 'Kisii': 348,
        'Kisumu': 401, 'Kitui': 198, 'Kwale': 531, 'Laikipia': 308,
        'Lamu': 621, 'Machakos': 88, 'Makueni': 126, 'Mandera': 1154,
        'Marsabit': 653, 'Meru': 301, 'Migori': 366, 'Mombasa': 544,
        'Muranga': 178, 'Nairobi': 84, 'Nakuru': 255, 'Nandi': 394,
        'Narok': 180, 'Nyamira': 338, 'Nyandarua': 223, 'Nyeri': 217,
        'Samburu': 441, 'Siaya': 460, 'Taita Taveta': 331, 'Tana River': 489,
        'Tharaka Nithi': 302, 'Trans Nzoia': 506, 'Turkana': 767, 'Uasin Gishu': 421,
        'Vihiga': 424, 'Wajir': 730, 'West Pokot': 528,
    },
    'Kakamega': {
        'Baringo': 185, 'Bomet': 184, 'Bungoma': 51, 'Busia': 100,
        'Elgeyo Marakwet': 136, 'Embu': 424, 'Garissa': 744, 'Homa Bay': 130,
        'Isiolo': 425, 'Kajiado': 443, 'Kakamega': 0, 'Kericho': 127,
        'Kiambu': 382, 'Kilifi': 961, 'Kirinyaga': 397, 'Kisii': 144,
        'Kisumu': 57, 'Kitui': 549, 'Kwale': 972, 'Laikipia': 308,
        'Lamu': 999, 'Machakos': 464, 'Makueni': 532, 'Mandera': 1197,
        'Marsabit': 575, 'Meru': 437, 'Migori': 207, 'Mombasa': 983,
        'Muranga': 390, 'Nairobi': 390, 'Nakuru': 217, 'Nandi': 57,
        'Narok': 265, 'Nyamira': 131, 'Nyandarua': 294, 'Nyeri': 346,
        'Samburu': 358, 'Siaya': 86, 'Taita Taveta': 774, 'Tana River': 833,
        'Tharaka Nithi': 475, 'Trans Nzoia': 117, 'Turkana': 444, 'Uasin Gishu': 85,
        'Vihiga': 31, 'Wajir': 826, 'West Pokot': 154,
    },
    'Kericho': {
        'Baringo': 162, 'Bomet': 63, 'Bungoma': 177, 'Busia': 216,
        'Elgeyo Marakwet': 174, 'Embu': 327, 'Garissa': 655, 'Homa Bay': 127,
        'Isiolo': 362, 'Kajiado': 316, 'Kakamega': 127, 'Kericho': 0,
        'Kiambu': 262, 'Kilifi': 838, 'Kirinyaga': 300, 'Kisii': 89,
        'Kisumu': 88, 'Kitui': 436, 'Kwale': 846, 'Laikipia': 243,
        'Lamu': 890, 'Machakos': 343, 'Makueni': 410, 'Mandera': 1177,
        'Marsabit': 574, 'Meru': 358, 'Migori': 161, 'Mombasa': 859,
        'Muranga': 285, 'Nairobi': 269, 'Nakuru': 120, 'Nandi': 86,
        'Narok': 138, 'Nyamira': 61, 'Nyandarua': 197, 'Nyeri': 250,
        'Samburu': 336, 'Siaya': 157, 'Taita Taveta': 647, 'Tana River': 729,
        'Tharaka Nithi': 392, 'Trans Nzoia': 213, 'Turkana': 525, 'Uasin Gishu': 132,
        'Vihiga': 108, 'Wajir': 783, 'West Pokot': 243,
    },
    'Kiambu': {
        'Baringo': 279, 'Bomet': 231, 'Bungoma': 429, 'Busia': 477,
        'Elgeyo Marakwet': 352, 'Embu': 135, 'Garissa': 436, 'Homa Bay': 370,
        'Isiolo': 255, 'Kajiado': 101, 'Kakamega': 382, 'Kericho': 262,
        'Kiambu': 0, 'Kilifi': 579, 'Kirinyaga': 123, 'Kisii': 317,
        'Kisumu': 351, 'Kitui': 180, 'Kwale': 597, 'Laikipia': 207,
        'Lamu': 632, 'Machakos': 82, 'Makueni': 150, 'Mandera': 1075,
        'Marsabit': 554, 'Meru': 209, 'Migori': 355, 'Mombasa': 605,
        'Muranga': 84, 'Nairobi': 18, 'Nakuru': 173, 'Nandi': 329,
        'Narok': 146, 'Nyamira': 300, 'Nyandarua': 124, 'Nyeri': 115,
        'Samburu': 339, 'Siaya': 417, 'Taita Taveta': 404, 'Tana River': 479,
        'Tharaka Nithi': 219, 'Trans Nzoia': 429, 'Turkana': 671, 'Uasin Gishu': 346,
        'Vihiga': 369, 'Wajir': 653, 'West Pokot': 446,
    },
    'Kilifi': {
        'Baringo': 841, 'Bomet': 796, 'Bungoma': 1008, 'Busia': 1054,
        'Elgeyo Marakwet': 921, 'Embu': 579, 'Garissa': 460, 'Homa Bay': 933,
        'Isiolo': 678, 'Kajiado': 531, 'Kakamega': 961, 'Kericho': 838,
        'Kiambu': 579, 'Kilifi': 0, 'Kirinyaga': 601, 'Kisii': 879,
        'Kisumu': 926, 'Kitui': 429, 'Kwale': 122, 'Laikipia': 726,
        'Lamu': 239, 'Machakos': 497, 'Makueni': 429, 'Mandera': 1154,
        'Marsabit': 922, 'Meru': 621, 'Migori': 894, 'Mombasa': 88,
        'Muranga': 589, 'Nairobi': 570, 'Nakuru': 749, 'Nandi': 909,
        'Narok': 707, 'Nyamira': 868, 'Nyandarua': 683, 'Nyeri': 643,
        'Samburu': 815, 'Siaya': 990, 'Taita Taveta': 234, 'Tana River': 305,
        'Tharaka Nithi': 587, 'Trans Nzoia': 1002, 'Turkana': 1187, 'Uasin Gishu': 922,
        'Vihiga': 946, 'Wajir': 790, 'West Pokot': 1013,
    },
    'Kirinyaga': {
        'Baringo': 244, 'Bomet': 293, 'Bungoma': 437, 'Busia': 497,
        'Elgeyo Marakwet': 325, 'Embu': 27, 'Garissa': 355, 'Homa Bay': 424,
        'Isiolo': 135, 'Kajiado': 217, 'Kakamega': 397, 'Kericho': 300,
        'Kiambu': 123, 'Kilifi': 601, 'Kirinyaga': 0, 'Kisii': 377,
        'Kisumu': 382, 'Kitui': 171, 'Kwale': 641, 'Laikipia': 126,
        'Lamu': 606, 'Machakos': 154, 'Makueni': 202, 'Mandera': 954,
        'Marsabit': 436, 'Meru': 86, 'Migori': 431, 'Mombasa': 643,
        'Muranga': 39, 'Nairobi': 139, 'Nakuru': 182, 'Nandi': 340,
        'Narok': 230, 'Nyamira': 352, 'Nyandarua': 104, 'Nyeri': 51,
        'Samburu': 239, 'Siaya': 454, 'Taita Taveta': 466, 'Tana River': 437,
        'Tharaka Nithi': 103, 'Trans Nzoia': 409, 'Turkana': 598, 'Uasin Gishu': 338,
        'Vihiga': 393, 'Wajir': 536, 'West Pokot': 416,
    },
    'Kisii': {
        'Baringo': 247, 'Bomet': 86, 'Bungoma': 189, 'Busia': 198,
        'Elgeyo Marakwet': 243, 'Embu': 402, 'Garissa': 732, 'Homa Bay': 54,
        'Isiolo': 448, 'Kajiado': 348, 'Kakamega': 144, 'Kericho': 89,
        'Kiambu': 317, 'Kilifi': 879, 'Kirinyaga': 377, 'Kisii': 0,
        'Kisumu': 88, 'Kitui': 497, 'Kwale': 875, 'Laikipia': 331,
        'Lamu': 949, 'Machakos': 393, 'Makueni': 458, 'Mandera': 1266,
        'Marsabit': 660, 'Meru': 441, 'Migori': 74, 'Mombasa': 891,
        'Muranga': 355, 'Nairobi': 320, 'Nakuru': 202, 'Nandi': 139,
        'Narok': 174, 'Nyamira': 28, 'Nyandarua': 277, 'Nyeri': 328,
        'Samburu': 425, 'Siaya': 119, 'Taita Taveta': 675, 'Tana River': 795,
        'Tharaka Nithi': 473, 'Trans Nzoia': 256, 'Turkana': 583, 'Uasin Gishu': 193,
        'Vihiga': 113, 'Wajir': 872, 'West Pokot': 292,
    },
    'Kisumu': {
        'Baringo': 198, 'Bomet': 136, 'Bungoma': 103, 'Busia': 128,
        'Elgeyo Marakwet': 171, 'Embu': 409, 'Garissa': 734, 'Homa Bay': 80,
        'Isiolo': 428, 'Kajiado': 401, 'Kakamega': 57, 'Kericho': 88,
        'Kiambu': 351, 'Kilifi': 926, 'Kirinyaga': 382, 'Kisii': 88,
        'Kisumu': 0, 'Kitui': 524, 'Kwale': 932, 'Laikipia': 308,
        'Lamu': 977, 'Machakos': 432, 'Makueni': 498, 'Mandera': 1222,
        'Marsabit': 605, 'Meru': 432, 'Migori': 153, 'Mombasa': 945,
        'Muranga': 370, 'Nairobi': 358, 'Nakuru': 200, 'Nandi': 66,
        'Narok': 223, 'Nyamira': 76, 'Nyandarua': 278, 'Nyeri': 331,
        'Samburu': 378, 'Siaya': 72, 'Taita Taveta': 732, 'Tana River': 815,
        'Tharaka Nithi': 468, 'Trans Nzoia': 170, 'Turkana': 497, 'Uasin Gishu': 117,
        'Vihiga': 26, 'Wajir': 841, 'West Pokot': 207,
    },
    'Kitui': {
        'Baringo': 413, 'Bomet': 409, 'Bungoma': 594, 'Busia': 647,
        'Elgeyo Marakwet': 493, 'Embu': 151, 'Garissa': 281, 'Homa Bay': 549,
        'Isiolo': 266, 'Kajiado': 198, 'Kakamega': 549, 'Kericho': 436,
        'Kiambu': 180, 'Kilifi': 429, 'Kirinyaga': 171, 'Kisii': 497,
        'Kisumu': 524, 'Kitui': 0, 'Kwale': 473, 'Laikipia': 298,
        'Lamu': 454, 'Machakos': 115, 'Makueni': 89, 'Mandera': 981,
        'Marsabit': 555, 'Meru': 205, 'Migori': 533, 'Mombasa': 473,
        'Muranga': 162, 'Nairobi': 180, 'Nakuru': 332, 'Nandi': 494,
        'Narok': 325, 'Nyamira': 478, 'Nyandarua': 259, 'Nyeri': 215,
        'Samburu': 397, 'Siaya': 593, 'Taita Taveta': 309, 'Tana River': 301,
        'Tharaka Nithi': 181, 'Trans Nzoia': 576, 'Turkana': 764, 'Uasin Gishu': 500,
        'Vihiga': 540, 'Wajir': 559, 'West Pokot': 586,
    },
    'Kwale': {
        'Baringo': 871, 'Bomet': 798, 'Bungoma': 1022, 'Busia': 1061,
        'Elgeyo Marakwet': 948, 'Embu': 622, 'Garissa': 559, 'Homa Bay': 927,
        'Isiolo': 736, 'Kajiado': 531, 'Kakamega': 972, 'Kericho': 846,
        'Kiambu': 597, 'Kilifi': 122, 'Kirinyaga': 641, 'Kisii': 875,
        'Kisumu': 932, 'Kitui': 473, 'Kwale': 0, 'Laikipia': 768,
        'Lamu': 359, 'Machakos': 516, 'Makueni': 450, 'Mandera': 1269,
        'Marsabit': 1000, 'Meru': 676, 'Migori': 880, 'Mombasa': 38,
        'Muranga': 622, 'Nairobi': 585, 'Nakuru': 770, 'Nandi': 922,
        'Narok': 710, 'Nyamira': 867, 'Nyandarua': 711, 'Nyeri': 678,
        'Samburu': 869, 'Siaya': 990, 'Taita Taveta': 201, 'Tana River': 413,
        'Tharaka Nithi': 645, 'Trans Nzoia': 1026, 'Turkana': 1238, 'Uasin Gishu': 942,
        'Vihiga': 953, 'Wajir': 894, 'West Pokot': 1041,
    },
    'Laikipia': {
        'Baringo': 131, 'Bomet': 263, 'Bungoma': 340, 'Busia': 405,
        'Elgeyo Marakwet': 211, 'Embu': 147, 'Garissa': 439, 'Homa Bay': 369,
        'Isiolo': 120, 'Kajiado': 308, 'Kakamega': 308, 'Kericho': 243,
        'Kiambu': 207, 'Kilifi': 726, 'Kirinyaga': 126, 'Kisii': 331,
        'Kisumu': 308, 'Kitui': 298, 'Kwale': 768, 'Laikipia': 0,
        'Lamu': 718, 'Machakos': 267, 'Makueni': 324, 'Mandera': 942,
        'Marsabit': 366, 'Meru': 132, 'Migori': 397, 'Mombasa': 768,
        'Muranga': 147, 'Nairobi': 224, 'Nakuru': 132, 'Nandi': 252,
        'Narok': 238, 'Nyamira': 302, 'Nyandarua': 93, 'Nyeri': 96,
        'Samburu': 135, 'Siaya': 379, 'Taita Taveta': 589, 'Tana River': 545,
        'Tharaka Nithi': 171, 'Trans Nzoia': 296, 'Turkana': 474, 'Uasin Gishu': 235,
        'Vihiga': 312, 'Wajir': 541, 'West Pokot': 297,
    },
    'Lamu': {
        'Baringo': 846, 'Bomet': 863, 'Bungoma': 1042, 'Busia': 1099,
        'Elgeyo Marakwet': 927, 'Embu': 579, 'Garissa': 331, 'Homa Bay': 1002,
        'Isiolo': 636, 'Kajiado': 621, 'Kakamega': 999, 'Kericho': 890,
        'Kiambu': 632, 'Kilifi': 239, 'Kirinyaga': 606, 'Kisii': 949,
        'Kisumu': 977, 'Kitui': 454, 'Kwale': 359, 'Laikipia': 718,
        'Lamu': 0, 'Machakos': 558, 'Makueni': 498, 'Mandera': 942,
        'Marsabit': 817, 'Meru': 591, 'Migori': 981, 'Mombasa': 324,
        'Muranga': 609, 'Nairobi': 629, 'Nakuru': 782, 'Nandi': 944,
        'Narok': 776, 'Nyamira': 932, 'Nyandarua': 705, 'Nyeri': 655,
        'Samburu': 772, 'Siaya': 1046, 'Taita Taveta': 417, 'Tana River': 178,
        'Tharaka Nithi': 552, 'Trans Nzoia': 1014, 'Turkana': 1135, 'Uasin Gishu': 942,
        'Vihiga': 992, 'Wajir': 617, 'West Pokot': 1017,
    },
    'Machakos': {
        'Baringo': 356, 'Bomet': 308, 'Bungoma': 512, 'Busia': 559,
        'Elgeyo Marakwet': 432, 'Embu': 151, 'Garissa': 392, 'Homa Bay': 447,
        'Isiolo': 285, 'Kajiado': 88, 'Kakamega': 464, 'Kericho': 343,
        'Kiambu': 82, 'Kilifi': 497, 'Kirinyaga': 154, 'Kisii': 393,
        'Kisumu': 432, 'Kitui': 115, 'Kwale': 516, 'Laikipia': 267,
        'Lamu': 558, 'Machakos': 0, 'Makueni': 68, 'Mandera': 1069,
        'Marsabit': 587, 'Meru': 228, 'Migori': 424, 'Mombasa': 524,
        'Muranga': 122, 'Nairobi': 74, 'Nakuru': 255, 'Nandi': 410,
        'Narok': 219, 'Nyamira': 378, 'Nyandarua': 197, 'Nyeri': 171,
        'Samburu': 392, 'Siaya': 497, 'Taita Taveta': 327, 'Tana River': 413,
        'Tharaka Nithi': 223, 'Trans Nzoia': 510, 'Turkana': 740, 'Uasin Gishu': 427,
        'Vihiga': 450, 'Wajir': 645, 'West Pokot': 525,
    },
    'Makueni': {
        'Baringo': 421, 'Bomet': 373, 'Bungoma': 580, 'Busia': 626,
        'Elgeyo Marakwet': 498, 'Embu': 192, 'Garissa': 366, 'Homa Bay': 512,
        'Isiolo': 324, 'Kajiado': 126, 'Kakamega': 532, 'Kericho': 410,
        'Kiambu': 150, 'Kilifi': 429, 'Kirinyaga': 202, 'Kisii': 458,
        'Kisumu': 498, 'Kitui': 89, 'Kwale': 450, 'Laikipia': 324,
        'Lamu': 498, 'Machakos': 68, 'Makueni': 0, 'Mandera': 1069,
        'Marsabit': 622, 'Meru': 263, 'Migori': 485, 'Mombasa': 456,
        'Muranga': 177, 'Nairobi': 142, 'Nakuru': 323, 'Nandi': 479,
        'Narok': 284, 'Nyamira': 443, 'Nyandarua': 262, 'Nyeri': 231,
        'Samburu': 441, 'Siaya': 564, 'Taita Taveta': 265, 'Tana River': 363,
        'Tharaka Nithi': 248, 'Trans Nzoia': 576, 'Turkana': 798, 'Uasin Gishu': 494,
        'Vihiga': 517, 'Wajir': 647, 'West Pokot': 591,
    },
    'Mandera': {
        'Baringo': 1025, 'Bomet': 1206, 'Bungoma': 1204, 'Busia': 1272,
        'Elgeyo Marakwet': 1062, 'Embu': 940, 'Garissa': 737, 'Homa Bay': 1296,
        'Isiolo': 836, 'Kajiado': 1154, 'Kakamega': 1197, 'Kericho': 1177,
        'Kiambu': 1075, 'Kilifi': 1154, 'Kirinyaga': 954, 'Kisii': 1266,
        'Kisumu': 1222, 'Kitui': 981, 'Kwale': 1269, 'Laikipia': 942,
        'Lamu': 942, 'Machakos': 1069, 'Makueni': 1069, 'Mandera': 0,
        'Marsabit': 626, 'Meru': 868, 'Migori': 1336, 'Mombasa': 1242,
        'Muranga': 992, 'Nairobi': 1088, 'Nakuru': 1075, 'Nandi': 1156,
        'Narok': 1170, 'Nyamira': 1238, 'Nyandarua': 1019, 'Nyeri': 983,
        'Samburu': 844, 'Siaya': 1282, 'Taita Taveta': 1219, 'Tana River': 859,
        'Tharaka Nithi': 856, 'Trans Nzoia': 1115, 'Turkana': 945, 'Uasin Gishu': 1112,
        'Vihiga': 1215, 'Wajir': 424, 'West Pokot': 1088,
    },
    'Marsabit': {
        'Baringo': 413, 'Bomet': 613, 'Bungoma': 579, 'Busia': 647,
        'Elgeyo Marakwet': 439, 'Embu': 437, 'Garissa': 487, 'Homa Bay': 682,
        'Isiolo': 302, 'Kajiado': 653, 'Kakamega': 575, 'Kericho': 574,
        'Kiambu': 554, 'Kilifi': 922, 'Kirinyaga': 436, 'Kisii': 660,
        'Kisumu': 605, 'Kitui': 555, 'Kwale': 1000, 'Laikipia': 366,
        'Lamu': 817, 'Machakos': 587, 'Makueni': 622, 'Mandera': 626,
        'Marsabit': 0, 'Meru': 360, 'Migori': 733, 'Mombasa': 990,
        'Muranga': 474, 'Nairobi': 571, 'Nakuru': 487, 'Nandi': 539,
        'Narok': 602, 'Nyamira': 632, 'Nyandarua': 458, 'Nyeri': 440,
        'Samburu': 239, 'Siaya': 662, 'Taita Taveta': 861, 'Tana River': 648,
        'Tharaka Nithi': 375, 'Trans Nzoia': 489, 'Turkana': 378, 'Uasin Gishu': 490,
        'Vihiga': 595, 'Wajir': 323, 'West Pokot': 462,
    },
    'Meru': {
        'Baringo': 265, 'Bomet': 362, 'Bungoma': 473, 'Busia': 536,
        'Elgeyo Marakwet': 343, 'Embu': 78, 'Garissa': 306, 'Homa Bay': 485,
        'Isiolo': 61, 'Kajiado': 301, 'Kakamega': 437, 'Kericho': 358,
        'Kiambu': 209, 'Kilifi': 621, 'Kirinyaga': 86, 'Kisii': 441,
        'Kisumu': 432, 'Kitui': 205, 'Kwale': 676, 'Laikipia': 132,
        'Lamu': 591, 'Machakos': 228, 'Makueni': 263, 'Mandera': 868,
        'Marsabit': 360, 'Meru': 0, 'Migori': 501, 'Mombasa': 672,
        'Muranga': 126, 'Nairobi': 224, 'Nakuru': 239, 'Nandi': 382,
        'Narok': 309, 'Nyamira': 414, 'Nyandarua': 165, 'Nyeri': 119,
        'Samburu': 196, 'Siaya': 505, 'Taita Taveta': 514, 'Tana River': 416,
        'Tharaka Nithi': 39, 'Trans Nzoia': 428, 'Turkana': 566, 'Uasin Gishu': 367,
        'Vihiga': 440, 'Wajir': 451, 'West Pokot': 427,
    },
    'Migori': {
        'Baringo': 321, 'Bomet': 138, 'Bungoma': 244, 'Busia': 235,
        'Elgeyo Marakwet': 316, 'Embu': 455, 'Garissa': 782, 'Homa Bay': 81,
        'Isiolo': 513, 'Kajiado': 366, 'Kakamega': 207, 'Kericho': 161,
        'Kiambu': 355, 'Kilifi': 894, 'Kirinyaga': 431, 'Kisii': 74,
        'Kisumu': 153, 'Kitui': 533, 'Kwale': 880, 'Laikipia': 397,
        'Lamu': 981, 'Machakos': 424, 'Makueni': 485, 'Mandera': 1336,
        'Marsabit': 733, 'Meru': 501, 'Migori': 0, 'Mombasa': 898,
        'Muranga': 405, 'Nairobi': 354, 'Nakuru': 267, 'Nandi': 211,
        'Narok': 211, 'Nyamira': 101, 'Nyandarua': 335, 'Nyeri': 385,
        'Samburu': 497, 'Siaya': 153, 'Taita Taveta': 680, 'Tana River': 834,
        'Tharaka Nithi': 529, 'Trans Nzoia': 323, 'Turkana': 649, 'Uasin Gishu': 266,
        'Vihiga': 176, 'Wajir': 938, 'West Pokot': 359,
    },
    'Mombasa': {
        'Baringo': 876, 'Bomet': 811, 'Bungoma': 1033, 'Busia': 1073,
        'Elgeyo Marakwet': 953, 'Embu': 622, 'Garissa': 539, 'Homa Bay': 944,
        'Isiolo': 730, 'Kajiado': 544, 'Kakamega': 983, 'Kericho': 859,
        'Kiambu': 605, 'Kilifi': 88, 'Kirinyaga': 643, 'Kisii': 891,
        'Kisumu': 945, 'Kitui': 473, 'Kwale': 38, 'Laikipia': 768,
        'Lamu': 324, 'Machakos': 524, 'Makueni': 456, 'Mandera': 1242,
        'Marsabit': 990, 'Meru': 672, 'Migori': 898, 'Mombasa': 0,
        'Muranga': 626, 'Nairobi': 594, 'Nakuru': 778, 'Nandi': 932,
        'Narok': 722, 'Nyamira': 882, 'Nyandarua': 717, 'Nyeri': 680,
        'Samburu': 867, 'Siaya': 1004, 'Taita Taveta': 219, 'Tana River': 387,
        'Tharaka Nithi': 641, 'Trans Nzoia': 1033, 'Turkana': 1237, 'Uasin Gishu': 950,
        'Vihiga': 965, 'Wajir': 872, 'West Pokot': 1046,
    },
    'Muranga': {
        'Baringo': 251, 'Bomet': 270, 'Bungoma': 433, 'Busia': 489,
        'Elgeyo Marakwet': 331, 'Embu': 54, 'Garissa': 377, 'Homa Bay': 405,
        'Isiolo': 174, 'Kajiado': 178, 'Kakamega': 390, 'Kericho': 285,
        'Kiambu': 84, 'Kilifi': 589, 'Kirinyaga': 39, 'Kisii': 355,
        'Kisumu': 370, 'Kitui': 162, 'Kwale': 622, 'Laikipia': 147,
        'Lamu': 609, 'Machakos': 122, 'Makueni': 177, 'Mandera': 992,
        'Marsabit': 474, 'Meru': 126, 'Migori': 405, 'Mombasa': 626,
        'Muranga': 0, 'Nairobi': 99, 'Nakuru': 173, 'Nandi': 333,
        'Narok': 200, 'Nyamira': 333, 'Nyandarua': 97, 'Nyeri': 54,
        'Samburu': 271, 'Siaya': 440, 'Taita Taveta': 441, 'Tana River': 446,
        'Tharaka Nithi': 138, 'Trans Nzoia': 414, 'Turkana': 621, 'Uasin Gishu': 338,
        'Vihiga': 383, 'Wajir': 572, 'West Pokot': 424,
    },
    'Nairobi': {
        'Baringo': 293, 'Bomet': 234, 'Bungoma': 439, 'Busia': 485,
        'Elgeyo Marakwet': 366, 'Embu': 148, 'Garissa': 443, 'Homa Bay': 373,
        'Isiolo': 273, 'Kajiado': 84, 'Kakamega': 390, 'Kericho': 269,
        'Kiambu': 18, 'Kilifi': 570, 'Kirinyaga': 139, 'Kisii': 320,
        'Kisumu': 358, 'Kitui': 180, 'Kwale': 585, 'Laikipia': 224,
        'Lamu': 629, 'Machakos': 74, 'Makueni': 142, 'Mandera': 1088,
        'Marsabit': 571, 'Meru': 224, 'Migori': 354, 'Mombasa': 594,
        'Muranga': 99, 'Nairobi': 0, 'Nakuru': 185, 'Nandi': 339,
        'Narok': 146, 'Nyamira': 304, 'Nyandarua': 140, 'Nyeri': 132,
        'Samburu': 356, 'Siaya': 423, 'Taita Taveta': 392, 'Tana River': 481,
        'Tharaka Nithi': 232, 'Trans Nzoia': 441, 'Turkana': 687, 'Uasin Gishu': 358,
        'Vihiga': 377, 'Wajir': 667, 'West Pokot': 459,
    },
    'Nakuru': {
        'Baringo': 117, 'Bomet': 131, 'Bungoma': 262, 'Busia': 317,
        'Elgeyo Marakwet': 181, 'Embu': 209, 'Garissa': 536, 'Homa Bay': 246,
        'Isiolo': 246, 'Kajiado': 255, 'Kakamega': 217, 'Kericho': 120,
        'Kiambu': 173, 'Kilifi': 749, 'Kirinyaga': 182, 'Kisii': 202,
        'Kisumu': 200, 'Kitui': 332, 'Kwale': 770, 'Laikipia': 132,
        'Lamu': 782, 'Machakos': 255, 'Makueni': 323, 'Mandera': 1075,
        'Marsabit': 487, 'Meru': 239, 'Migori': 267, 'Mombasa': 778,
        'Muranga': 173, 'Nairobi': 185, 'Nakuru': 0, 'Nandi': 162,
        'Narok': 120, 'Nyamira': 177, 'Nyandarua': 80, 'Nyeri': 132,
        'Samburu': 248, 'Siaya': 271, 'Taita Taveta': 576, 'Tana River': 617,
        'Tharaka Nithi': 271, 'Trans Nzoia': 255, 'Turkana': 518, 'Uasin Gishu': 173,
        'Vihiga': 212, 'Wajir': 672, 'West Pokot': 273,
    },
    'Nandi': {
        'Baringo': 135, 'Bomet': 150, 'Bungoma': 101, 'Busia': 157,
        'Elgeyo Marakwet': 107, 'Embu': 367, 'Garissa': 687, 'Homa Bay': 146,
        'Isiolo': 371, 'Kajiado': 394, 'Kakamega': 57, 'Kericho': 86,
        'Kiambu': 329, 'Kilifi': 909, 'Kirinyaga': 340, 'Kisii': 139,
        'Kisumu': 66, 'Kitui': 494, 'Kwale': 922, 'Laikipia': 252,
        'Lamu': 944, 'Machakos': 410, 'Makueni': 479, 'Mandera': 1156,
        'Marsabit': 539, 'Meru': 382, 'Migori': 211, 'Mombasa': 932,
        'Muranga': 333, 'Nairobi': 339, 'Nakuru': 162, 'Nandi': 0,
        'Narok': 221, 'Nyamira': 116, 'Nyandarua': 239, 'Nyeri': 289,
        'Samburu': 313, 'Siaya': 130, 'Taita Taveta': 725, 'Tana River': 776,
        'Tharaka Nithi': 418, 'Trans Nzoia': 127, 'Turkana': 447, 'Uasin Gishu': 55,
        'Vihiga': 61, 'Wajir': 778, 'West Pokot': 158,
    },
    'Narok': {
        'Baringo': 232, 'Bomet': 90, 'Bungoma': 316, 'Busia': 351,
        'Elgeyo Marakwet': 282, 'Embu': 252, 'Garissa': 574, 'Homa Bay': 228,
        'Isiolo': 335, 'Kajiado': 180, 'Kakamega': 265, 'Kericho': 138,
        'Kiambu': 146, 'Kilifi': 707, 'Kirinyaga': 230, 'Kisii': 174,
        'Kisumu': 223, 'Kitui': 325, 'Kwale': 710, 'Laikipia': 238,
        'Lamu': 776, 'Machakos': 219, 'Makueni': 284, 'Mandera': 1170,
        'Marsabit': 602, 'Meru': 309, 'Migori': 211, 'Mombasa': 722,
        'Muranga': 200, 'Nairobi': 146, 'Nakuru': 120, 'Nandi': 221,
        'Narok': 0, 'Nyamira': 161, 'Nyandarua': 151, 'Nyeri': 190,
        'Samburu': 366, 'Siaya': 282, 'Taita Taveta': 510, 'Tana River': 625,
        'Tharaka Nithi': 332, 'Trans Nzoia': 340, 'Turkana': 632, 'Uasin Gishu': 255,
        'Vihiga': 244, 'Wajir': 759, 'West Pokot': 366,
    },
    'Nyamira': {
        'Baringo': 220, 'Bomet': 70, 'Bungoma': 178, 'Busia': 197,
        'Elgeyo Marakwet': 219, 'Embu': 379, 'Garissa': 707, 'Homa Bay': 72,
        'Isiolo': 421, 'Kajiado': 338, 'Kakamega': 131, 'Kericho': 61,
        'Kiambu': 300, 'Kilifi': 868, 'Kirinyaga': 352, 'Kisii': 28,
        'Kisumu': 76, 'Kitui': 478, 'Kwale': 867, 'Laikipia': 302,
        'Lamu': 932, 'Machakos': 378, 'Makueni': 443, 'Mandera': 1238,
        'Marsabit': 632, 'Meru': 414, 'Migori': 101, 'Mombasa': 882,
        'Muranga': 333, 'Nairobi': 304, 'Nakuru': 177, 'Nandi': 116,
        'Narok': 161, 'Nyamira': 0, 'Nyandarua': 251, 'Nyeri': 304,
        'Samburu': 397, 'Siaya': 123, 'Taita Taveta': 667, 'Tana River': 775,
        'Tharaka Nithi': 447, 'Trans Nzoia': 239, 'Turkana': 562, 'Uasin Gishu': 170,
        'Vihiga': 101, 'Wajir': 844, 'West Pokot': 273,
    },
    'Nyandarua': {
        'Baringo': 159, 'Bomet': 197, 'Bungoma': 338, 'Busia': 394,
        'Elgeyo Marakwet': 238, 'Embu': 131, 'Garissa': 458, 'Homa Bay': 323,
        'Isiolo': 185, 'Kajiado': 223, 'Kakamega': 294, 'Kericho': 197,
        'Kiambu': 124, 'Kilifi': 683, 'Kirinyaga': 104, 'Kisii': 277,
        'Kisumu': 278, 'Kitui': 259, 'Kwale': 711, 'Laikipia': 93,
        'Lamu': 705, 'Machakos': 197, 'Makueni': 262, 'Mandera': 1019,
        'Marsabit': 458, 'Meru': 165, 'Migori': 335, 'Mombasa': 717,
        'Muranga': 97, 'Nairobi': 140, 'Nakuru': 80, 'Nandi': 239,
        'Narok': 151, 'Nyamira': 251, 'Nyandarua': 0, 'Nyeri': 53,
        'Samburu': 227, 'Siaya': 351, 'Taita Taveta': 524, 'Tana River': 539,
        'Tharaka Nithi': 196, 'Trans Nzoia': 319, 'Turkana': 547, 'Uasin Gishu': 240,
        'Vihiga': 290, 'Wajir': 610, 'West Pokot': 331,
    },
    'Nyeri': {
        'Baringo': 198, 'Bomet': 247, 'Bungoma': 387, 'Busia': 446,
        'Elgeyo Marakwet': 279, 'Embu': 78, 'Garissa': 405, 'Homa Bay': 374,
        'Isiolo': 150, 'Kajiado': 217, 'Kakamega': 346, 'Kericho': 250,
        'Kiambu': 115, 'Kilifi': 643, 'Kirinyaga': 51, 'Kisii': 328,
        'Kisumu': 331, 'Kitui': 215, 'Kwale': 678, 'Laikipia': 96,
        'Lamu': 655, 'Machakos': 171, 'Makueni': 231, 'Mandera': 983,
        'Marsabit': 440, 'Meru': 119, 'Migori': 385, 'Mombasa': 680,
        'Muranga': 54, 'Nairobi': 132, 'Nakuru': 132, 'Nandi': 289,
        'Narok': 190, 'Nyamira': 304, 'Nyandarua': 53, 'Nyeri': 0,
        'Samburu': 224, 'Siaya': 404, 'Taita Taveta': 494, 'Tana River': 487,
        'Tharaka Nithi': 144, 'Trans Nzoia': 363, 'Turkana': 568, 'Uasin Gishu': 289,
        'Vihiga': 343, 'Wajir': 568, 'West Pokot': 371,
    },
    'Samburu': {
        'Baringo': 180, 'Bomet': 374, 'Bungoma': 374, 'Busia': 443,
        'Elgeyo Marakwet': 227, 'Embu': 251, 'Garissa': 459, 'Homa Bay': 451,
        'Isiolo': 139, 'Kajiado': 441, 'Kakamega': 358, 'Kericho': 336,
        'Kiambu': 339, 'Kilifi': 815, 'Kirinyaga': 239, 'Kisii': 425,
        'Kisumu': 378, 'Kitui': 397, 'Kwale': 869, 'Laikipia': 135,
        'Lamu': 772, 'Machakos': 392, 'Makueni': 441, 'Mandera': 844,
        'Marsabit': 239, 'Meru': 196, 'Migori': 497, 'Mombasa': 867,
        'Muranga': 271, 'Nairobi': 356, 'Nakuru': 248, 'Nandi': 313,
        'Narok': 366, 'Nyamira': 397, 'Nyandarua': 227, 'Nyeri': 224,
        'Samburu': 0, 'Siaya': 441, 'Taita Taveta': 702, 'Tana River': 594,
        'Tharaka Nithi': 230, 'Trans Nzoia': 300, 'Turkana': 371, 'Uasin Gishu': 273,
        'Vihiga': 373, 'Wajir': 470, 'West Pokot': 285,
    },
    'Siaya': {
        'Baringo': 265, 'Bomet': 193, 'Bungoma': 103, 'Busia': 82,
        'Elgeyo Marakwet': 223, 'Embu': 481, 'Garissa': 807, 'Homa Bay': 74,
        'Isiolo': 498, 'Kajiado': 460, 'Kakamega': 86, 'Kericho': 157,
        'Kiambu': 417, 'Kilifi': 990, 'Kirinyaga': 454, 'Kisii': 119,
        'Kisumu': 72, 'Kitui': 593, 'Kwale': 990, 'Laikipia': 379,
        'Lamu': 1046, 'Machakos': 497, 'Makueni': 564, 'Mandera': 1282,
        'Marsabit': 662, 'Meru': 505, 'Migori': 153, 'Mombasa': 1004,
        'Muranga': 440, 'Nairobi': 423, 'Nakuru': 271, 'Nandi': 130,
        'Narok': 282, 'Nyamira': 123, 'Nyandarua': 351, 'Nyeri': 404,
        'Samburu': 441, 'Siaya': 0, 'Taita Taveta': 790, 'Tana River': 886,
        'Tharaka Nithi': 540, 'Trans Nzoia': 194, 'Turkana': 516, 'Uasin Gishu': 171,
        'Vihiga': 69, 'Wajir': 907, 'West Pokot': 231,
    },
    'Taita Taveta': {
        'Baringo': 682, 'Bomet': 598, 'Bungoma': 824, 'Busia': 861,
        'Elgeyo Marakwet': 756, 'Embu': 451, 'Garissa': 482, 'Homa Bay': 726,
        'Isiolo': 575, 'Kajiado': 331, 'Kakamega': 774, 'Kericho': 647,
        'Kiambu': 404, 'Kilifi': 234, 'Kirinyaga': 466, 'Kisii': 675,
        'Kisumu': 732, 'Kitui': 309, 'Kwale': 201, 'Laikipia': 589,
        'Lamu': 417, 'Machakos': 327, 'Makueni': 265, 'Mandera': 1219,
        'Marsabit': 861, 'Meru': 514, 'Migori': 680, 'Mombasa': 219,
        'Muranga': 441, 'Nairobi': 392, 'Nakuru': 576, 'Nandi': 725,
        'Narok': 510, 'Nyamira': 667, 'Nyandarua': 524, 'Nyeri': 494,
        'Samburu': 702, 'Siaya': 790, 'Taita Taveta': 0, 'Tana River': 379,
        'Tharaka Nithi': 490, 'Trans Nzoia': 832, 'Turkana': 1062, 'Uasin Gishu': 748,
        'Vihiga': 755, 'Wajir': 814, 'West Pokot': 849,
    },
    'Tana River': {
        'Baringo': 675, 'Bomet': 709, 'Bungoma': 875, 'Busia': 933,
        'Elgeyo Marakwet': 755, 'Embu': 409, 'Garissa': 163, 'Homa Bay': 846,
        'Isiolo': 458, 'Kajiado': 489, 'Kakamega': 833, 'Kericho': 729,
        'Kiambu': 479, 'Kilifi': 305, 'Kirinyaga': 437, 'Kisii': 795,
        'Kisumu': 815, 'Kitui': 301, 'Kwale': 413, 'Laikipia': 545,
        'Lamu': 178, 'Machakos': 413, 'Makueni': 363, 'Mandera': 859,
        'Marsabit': 648, 'Meru': 416, 'Migori': 834, 'Mombasa': 387,
        'Muranga': 446, 'Nairobi': 481, 'Nakuru': 617, 'Nandi': 776,
        'Narok': 625, 'Nyamira': 775, 'Nyandarua': 539, 'Nyeri': 487,
        'Samburu': 594, 'Siaya': 886, 'Taita Taveta': 379, 'Tana River': 0,
        'Tharaka Nithi': 377, 'Trans Nzoia': 841, 'Turkana': 957, 'Uasin Gishu': 774,
        'Vihiga': 829, 'Wajir': 486, 'West Pokot': 842,
    },
    'Tharaka Nithi': {
        'Baringo': 302, 'Bomet': 392, 'Bungoma': 510, 'Busia': 574,
        'Elgeyo Marakwet': 382, 'Embu': 84, 'Garissa': 269, 'Homa Bay': 517,
        'Isiolo': 90, 'Kajiado': 302, 'Kakamega': 475, 'Kericho': 392,
        'Kiambu': 219, 'Kilifi': 587, 'Kirinyaga': 103, 'Kisii': 473,
        'Kisumu': 468, 'Kitui': 181, 'Kwale': 645, 'Laikipia': 171,
        'Lamu': 552, 'Machakos': 223, 'Makueni': 248, 'Mandera': 856,
        'Marsabit': 375, 'Meru': 39, 'Migori': 529, 'Mombasa': 641,
        'Muranga': 138, 'Nairobi': 232, 'Nakuru': 271, 'Nandi': 418,
        'Narok': 332, 'Nyamira': 447, 'Nyandarua': 196, 'Nyeri': 144,
        'Samburu': 230, 'Siaya': 540, 'Taita Taveta': 490, 'Tana River': 377,
        'Tharaka Nithi': 0, 'Trans Nzoia': 467, 'Turkana': 601, 'Uasin Gishu': 405,
        'Vihiga': 475, 'Wajir': 435, 'West Pokot': 467,
    },
    'Trans Nzoia': {
        'Baringo': 166, 'Bomet': 275, 'Bungoma': 96, 'Busia': 158,
        'Elgeyo Marakwet': 85, 'Embu': 436, 'Garissa': 732, 'Homa Bay': 246,
        'Isiolo': 400, 'Kajiado': 506, 'Kakamega': 117, 'Kericho': 213,
        'Kiambu': 429, 'Kilifi': 1002, 'Kirinyaga': 409, 'Kisii': 256,
        'Kisumu': 170, 'Kitui': 576, 'Kwale': 1026, 'Laikipia': 296,
        'Lamu': 1014, 'Machakos': 510, 'Makueni': 576, 'Mandera': 1115,
        'Marsabit': 489, 'Meru': 428, 'Migori': 323, 'Mombasa': 1033,
        'Muranga': 414, 'Nairobi': 441, 'Nakuru': 255, 'Nandi': 127,
        'Narok': 340, 'Nyamira': 239, 'Nyandarua': 319, 'Nyeri': 363,
        'Samburu': 300, 'Siaya': 194, 'Taita Taveta': 832, 'Tana River': 841,
        'Tharaka Nithi': 467, 'Trans Nzoia': 0, 'Turkana': 327, 'Uasin Gishu': 85,
        'Vihiga': 148, 'Wajir': 765, 'West Pokot': 36,
    },
    'Turkana': {
        'Baringo': 402, 'Bomet': 587, 'Bungoma': 413, 'Busia': 456,
        'Elgeyo Marakwet': 352, 'Embu': 614, 'Garissa': 811, 'Homa Bay': 572,
        'Isiolo': 510, 'Kajiado': 767, 'Kakamega': 444, 'Kericho': 525,
        'Kiambu': 671, 'Kilifi': 1187, 'Kirinyaga': 598, 'Kisii': 583,
        'Kisumu': 497, 'Kitui': 764, 'Kwale': 1238, 'Laikipia': 474,
        'Lamu': 1135, 'Machakos': 740, 'Makueni': 798, 'Mandera': 945,
        'Marsabit': 378, 'Meru': 566, 'Migori': 649, 'Mombasa': 1237,
        'Muranga': 621, 'Nairobi': 687, 'Nakuru': 518, 'Nandi': 447,
        'Narok': 632, 'Nyamira': 562, 'Nyandarua': 547, 'Nyeri': 568,
        'Samburu': 371, 'Siaya': 516, 'Taita Taveta': 1062, 'Tana River': 957,
        'Tharaka Nithi': 601, 'Trans Nzoia': 327, 'Turkana': 0, 'Uasin Gishu': 394,
        'Vihiga': 475, 'Wajir': 699, 'West Pokot': 292,
    },
    'Uasin Gishu': {
        'Baringo': 105, 'Bomet': 196, 'Bungoma': 107, 'Busia': 174,
        'Elgeyo Marakwet': 53, 'Embu': 364, 'Garissa': 674, 'Homa Bay': 198,
        'Isiolo': 348, 'Kajiado': 421, 'Kakamega': 85, 'Kericho': 132,
        'Kiambu': 346, 'Kilifi': 922, 'Kirinyaga': 338, 'Kisii': 193,
        'Kisumu': 117, 'Kitui': 500, 'Kwale': 942, 'Laikipia': 235,
        'Lamu': 942, 'Machakos': 427, 'Makueni': 494, 'Mandera': 1112,
        'Marsabit': 490, 'Meru': 367, 'Migori': 266, 'Mombasa': 950,
        'Muranga': 338, 'Nairobi': 358, 'Nakuru': 173, 'Nandi': 55,
        'Narok': 255, 'Nyamira': 170, 'Nyandarua': 240, 'Nyeri': 289,
        'Samburu': 273, 'Siaya': 171, 'Taita Taveta': 748, 'Tana River': 774,
        'Tharaka Nithi': 405, 'Trans Nzoia': 85, 'Turkana': 394, 'Uasin Gishu': 0,
        'Vihiga': 105, 'Wajir': 742, 'West Pokot': 111,
    },
    'Vihiga': {
        'Baringo': 196, 'Bomet': 159, 'Bungoma': 77, 'Busia': 108,
        'Elgeyo Marakwet': 158, 'Embu': 421, 'Garissa': 744, 'Homa Bay': 99,
        'Isiolo': 431, 'Kajiado': 424, 'Kakamega': 31, 'Kericho': 108,
        'Kiambu': 369, 'Kilifi': 946, 'Kirinyaga': 393, 'Kisii': 113,
        'Kisumu': 26, 'Kitui': 540, 'Kwale': 953, 'Laikipia': 312,
        'Lamu': 992, 'Machakos': 450, 'Makueni': 517, 'Mandera': 1215,
        'Marsabit': 595, 'Meru': 440, 'Migori': 176, 'Mombasa': 965,
        'Muranga': 383, 'Nairobi': 377, 'Nakuru': 212, 'Nandi': 61,
        'Narok': 244, 'Nyamira': 101, 'Nyandarua': 290, 'Nyeri': 343,
        'Samburu': 373, 'Siaya': 69, 'Taita Taveta': 755, 'Tana River': 829,
        'Tharaka Nithi': 475, 'Trans Nzoia': 148, 'Turkana': 475, 'Uasin Gishu': 105,
        'Vihiga': 0, 'Wajir': 840, 'West Pokot': 184,
    },
    'Wajir': {
        'Baringo': 644, 'Bomet': 802, 'Bungoma': 844, 'Busia': 913,
        'Elgeyo Marakwet': 697, 'Embu': 520, 'Garissa': 338, 'Homa Bay': 907,
        'Isiolo': 427, 'Kajiado': 730, 'Kakamega': 826, 'Kericho': 783,
        'Kiambu': 653, 'Kilifi': 790, 'Kirinyaga': 536, 'Kisii': 872,
        'Kisumu': 841, 'Kitui': 559, 'Kwale': 894, 'Laikipia': 541,
        'Lamu': 617, 'Machakos': 645, 'Makueni': 647, 'Mandera': 424,
        'Marsabit': 323, 'Meru': 451, 'Migori': 938, 'Mombasa': 872,
        'Muranga': 572, 'Nairobi': 667, 'Nakuru': 672, 'Nandi': 778,
        'Narok': 759, 'Nyamira': 844, 'Nyandarua': 610, 'Nyeri': 568,
        'Samburu': 470, 'Siaya': 907, 'Taita Taveta': 814, 'Tana River': 486,
        'Tharaka Nithi': 435, 'Trans Nzoia': 765, 'Turkana': 699, 'Uasin Gishu': 742,
        'Vihiga': 840, 'Wajir': 0, 'West Pokot': 747,
    },
    'West Pokot': {
        'Baringo': 173, 'Bomet': 305, 'Bungoma': 131, 'Busia': 190,
        'Elgeyo Marakwet': 93, 'Embu': 441, 'Garissa': 726, 'Homa Bay': 282,
        'Isiolo': 394, 'Kajiado': 528, 'Kakamega': 154, 'Kericho': 243,
        'Kiambu': 446, 'Kilifi': 1013, 'Kirinyaga': 416, 'Kisii': 292,
        'Kisumu': 207, 'Kitui': 586, 'Kwale': 1041, 'Laikipia': 297,
        'Lamu': 1017, 'Machakos': 525, 'Makueni': 591, 'Mandera': 1088,
        'Marsabit': 462, 'Meru': 427, 'Migori': 359, 'Mombasa': 1046,
        'Muranga': 424, 'Nairobi': 459, 'Nakuru': 273, 'Nandi': 158,
        'Narok': 366, 'Nyamira': 273, 'Nyandarua': 331, 'Nyeri': 371,
        'Samburu': 285, 'Siaya': 231, 'Taita Taveta': 849, 'Tana River': 842,
        'Tharaka Nithi': 467, 'Trans Nzoia': 36, 'Turkana': 292, 'Uasin Gishu': 111,
        'Vihiga': 184, 'Wajir': 747, 'West Pokot': 0,
    },
}

# Unknown county pair → assume very far (no proximity bonus)
_UNKNOWN_DISTANCE = 999


def get_distance(county_a: str, county_b: str) -> int:
    """Return approximate road distance in km between two county centres."""
    return COUNTY_DISTANCE.get(county_a, {}).get(county_b, _UNKNOWN_DISTANCE)


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return exact great-circle distance in km using Haversine formula."""
    # Radius of the earth in km
    R = 6371.0
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return round(distance, 2)


def proximity_score(distance_km: float) -> int:
    """Convert a distance in km to a 0-10 proximity score."""
    if distance_km == 0:
        return 10
    if distance_km <= 5:
        return 10
    if distance_km <= 15:
        return 8
    if distance_km <= 30:
        return 6
    if distance_km <= 80:
        return 4
    if distance_km <= 150:
        return 2
    return 0



# ---------------------------------------------------------------------------
# 4. Baseline (heuristic) explanation generator
#    Used when both Groq and Gemini are unavailable.
# ---------------------------------------------------------------------------

def _baseline_explanation(
    donor: "Donor",
    requested_blood_type: str,
    days_since_last: int | None,
    distance_km: int,
    prox_score: int,
    total_score: int,
) -> str:
    """Produce a structured, readable explanation from first principles."""
    parts: list[str] = []

    # Compatibility sentence
    if donor.blood_type == "O-":
        parts.append(f"{donor.name} is O- (universal donor) and can donate to anyone, including {requested_blood_type}.")
    elif donor.blood_type == requested_blood_type:
        parts.append(f"{donor.name} is {donor.blood_type}, an exact match for the requested {requested_blood_type}.")
    else:
        parts.append(f"{donor.name} is {donor.blood_type}, which is compatible with the requested {requested_blood_type}.")

    # Eligibility sentence
    if days_since_last is None:
        parts.append("No previous donation is recorded, so they are immediately eligible.")
    else:
        parts.append(f"Their last donation was {days_since_last} days ago, which is past the 90-day safety window.")

    # Proximity sentence
    if distance_km == 0:
        parts.append(f"They are based in {donor.county}, the same county as the requesting hospital (maximum proximity score).")
    elif prox_score > 0:
        parts.append(f"They are approximately {distance_km} km away in {donor.county} (proximity score: {prox_score}/10).")
    else:
        parts.append(f"They are {distance_km} km away in {donor.county}. Distance reduces their overall rank but compatibility and eligibility still qualify them.")

    parts.append(f"Overall match score: {total_score}/100.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 5. AI-generated explanation via Groq → Gemini → baseline cascade
# ---------------------------------------------------------------------------

def _ai_explanation(
    donor: "Donor",
    requested_blood_type: str,
    days_since_last: int | None,
    distance_km: int,
    prox_score: int,
    compat_score: int,
    elig_score: int,
    total_score: int,
) -> str:
    """
    Call Groq first, Gemini second, baseline third.
    Returns a concise 1-3 sentence plain-English explanation.
    """
    try:
        from app.utils.ai_clients import get_ai_cascade
        cascade = get_ai_cascade()
    except Exception as exc:
        logger.warning("[Matching] Could not load AI cascade: %s", exc)
        return _baseline_explanation(
            donor, requested_blood_type, days_since_last,
            distance_km, prox_score, total_score
        )

    eligibility_phrase = (
        "no previous donation recorded (immediately eligible)"
        if days_since_last is None
        else f"last donated {days_since_last} days ago (90-day rule satisfied)"
    )

    prompt = (
        "You are a clinical matching system assistant for a blood donation platform in Kenya. "
        "Write exactly 2 concise sentences (no lists, no markdown, no bullet points) explaining "
        "why this donor is a good match for the blood request. Be factual and reassuring.\n\n"
        f"Donor name: {donor.name}\n"
        f"Donor blood type: {donor.blood_type}\n"
        f"Requested blood type: {requested_blood_type}\n"
        f"Eligibility: {eligibility_phrase}\n"
        f"Distance from hospital: {distance_km} km (donor county: {donor.county})\n"
        f"Scores — Compatibility: {compat_score}/60, Eligibility: {elig_score}/30, "
        f"Proximity: {prox_score}/10, Total: {total_score}/100\n\n"
        "2-sentence explanation:"
    )

    result = cascade.generate(prompt, max_tokens=120, temperature=0.35)

    if result:
        # Sanitise — strip any stray markdown
        result = result.replace("**", "").replace("*", "").replace("#", "").strip()
        return result

    # Both models exhausted → use baseline
    return _baseline_explanation(
        donor, requested_blood_type, days_since_last,
        distance_km, prox_score, total_score
    )


# ---------------------------------------------------------------------------
# 6. Public API
# ---------------------------------------------------------------------------

def score_donor(
    donor: "Donor",
    requested_blood_type: str,
    hospital: "Hospital",
    reference_date: date | None = None,
) -> dict[str, Any] | None:
    """
    Score a single donor against a blood request.

    Returns a result dict if the donor passes both the compatibility and
    eligibility filters, or None if they do not qualify.

    Result keys:
      donor           — the Donor ORM object
      score           — int 0-100
      compat_score    — int (0 or 60)
      elig_score      — int (0 or 30)
      prox_score      — int (0-10)
      compatible      — bool
      eligible        — bool
      days_since_last — int | None
      distance_km     — float
      reasons         — list[str]  (breakdown labels visible to judges)
      explanation     — str        (human-readable AI/baseline narrative)
    """
    # --- Filter 1: compatibility ---
    if not is_compatible(donor.blood_type, requested_blood_type):
        return None

    # --- Filter 2: eligibility ---
    eligible, days_since_last = is_eligible(donor, reference_date)
    if not eligible:
        return None

    # --- Score components ---
    compat_score = 60
    elig_score = 30

    def _normalize_location(value: str | None) -> str:
        return str(value or "").strip().lower()

    donor_county = _normalize_location(donor.county)
    hospital_county = _normalize_location(hospital.county)
    donor_subcounty = _normalize_location(donor.subcounty)
    hospital_subcounty = _normalize_location(hospital.subcounty)
    donor_ward = _normalize_location(donor.ward)
    hospital_ward = _normalize_location(hospital.ward)

    same_ward = donor_ward and hospital_ward and donor_ward == hospital_ward
    same_subcounty = donor_subcounty and hospital_subcounty and donor_subcounty == hospital_subcounty
    same_county = donor_county and hospital_county and donor_county == hospital_county

    # Precise GPS location check
    gps_active = False
    if (donor.latitude is not None and donor.longitude is not None and
            hospital.latitude is not None and hospital.longitude is not None):
        distance_km = calculate_haversine_distance(
            donor.latitude, donor.longitude,
            hospital.latitude, hospital.longitude
        )
        gps_active = True
        locality_label = "exact GPS distance"
    elif same_ward:
        distance_km = 2.0
        locality_label = "same ward/locality"
    elif same_subcounty:
        distance_km = 4.0
        locality_label = "same subcounty"
    elif same_county:
        distance_km = 10.0
        locality_label = "same county"
    else:
        # Fall back to county headquarters distance when no finer locality data is available
        distance_km = float(get_distance(hospital.county, donor.county))
        locality_label = "county-level estimate"

    prox_score = proximity_score(distance_km)
    total_score = compat_score + elig_score + prox_score

    # --- Breakdown reasons (visible to judges) ---
    if gps_active:
        dist_label = f"~{distance_km} km (exact GPS match)"
    else:
        dist_label = f"~{distance_km} km ({locality_label})"

    reasons: list[str] = [
        f"Blood type {donor.blood_type} is compatible with {requested_blood_type} (+{compat_score} pts)",
        (
            "No prior donation recorded — eligible (+30 pts)"
            if days_since_last is None
            else f"Last donated {days_since_last} days ago ≥ 90-day rule (+{elig_score} pts)"
        ),
        f"{dist_label} (+{prox_score} pts)",
    ]

    # --- AI narrative ---
    explanation = _ai_explanation(
        donor, requested_blood_type, days_since_last,
        int(distance_km), prox_score, compat_score, elig_score, total_score
    )

    return {
        "donor":           donor,
        "score":           total_score,
        "compat_score":    compat_score,
        "elig_score":      elig_score,
        "prox_score":      prox_score,
        "compatible":      True,
        "eligible":        True,
        "days_since_last": days_since_last,
        "distance_km":     distance_km,
        "reasons":         reasons,
        "explanation":     explanation,
    }


def rank_donors_for_request(
    requested_blood_type: str,
    hospital: "Hospital",
    reference_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Filter and rank all registered donors for a given blood request.

    Donors are sorted by total_score descending, then by name ascending for
    deterministic ordering when scores are equal.

    Only donors that pass BOTH compatibility AND eligibility checks are
    included in the result.
    """
    results: list[dict[str, Any]] = []

    for donor in Donor.query.all():
        result = score_donor(
            donor,
            requested_blood_type,
            hospital,
            reference_date,
        )
        if result is not None:
            results.append(result)

    results.sort(key=lambda r: (-r["score"], r["distance_km"], r["donor"].name))
    return results

