"""
Vingo — City configuration and shared category mappings.

Supports major Indian metros for C2C marketplace research.
Each city has platform-specific identifiers (OLX location ID, Quikr URL slug).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CityConfig:
    """Configuration for a single city across all supported platforms."""
    name: str
    display_name: str
    olx_location_id: str
    olx_slug: str
    quikr_slug: str


# ── Supported Cities ────────────────────────────────────────────────────────
# OLX location IDs extracted from OLX India URL patterns (g<id>)
# Quikr slugs are city names used in URL paths

CITIES: dict[str, CityConfig] = {
    "bangalore": CityConfig(
        name="bangalore",
        display_name="Bangalore",
        olx_location_id="4058803",
        olx_slug="bangalore",
        quikr_slug="bangalore",
    ),
    "mumbai": CityConfig(
        name="mumbai",
        display_name="Mumbai",
        olx_location_id="4058997",
        olx_slug="mumbai",
        quikr_slug="mumbai",
    ),
    "delhi": CityConfig(
        name="delhi",
        display_name="Delhi",
        olx_location_id="4058659",
        olx_slug="delhi",
        quikr_slug="delhi",
    ),
    "hyderabad": CityConfig(
        name="hyderabad",
        display_name="Hyderabad",
        olx_location_id="4058526",
        olx_slug="hyderabad",
        quikr_slug="hyderabad",
    ),
    "chennai": CityConfig(
        name="chennai",
        display_name="Chennai",
        olx_location_id="4059162",
        olx_slug="chennai",
        quikr_slug="chennai",
    ),
    "pune": CityConfig(
        name="pune",
        display_name="Pune",
        olx_location_id="4059014",
        olx_slug="pune",
        quikr_slug="pune",
    ),
    "kolkata": CityConfig(
        name="kolkata",
        display_name="Kolkata",
        olx_location_id="4157275",
        olx_slug="kolkata",
        quikr_slug="kolkata",
    ),
    "ahmedabad": CityConfig(
        name="ahmedabad",
        display_name="Ahmedabad",
        olx_location_id="4058677",
        olx_slug="ahmedabad",
        quikr_slug="ahmedabad",
    ),
    "jaipur": CityConfig(
        name="jaipur",
        display_name="Jaipur",
        olx_location_id="4059123",
        olx_slug="jaipur",
        quikr_slug="jaipur",
    ),
}


# ── OLX Category Definitions ───────────────────────────────────────────────
# Tuple: (category_id, url_slug)
# These are OLX India-wide category identifiers (not city-specific)

OLX_CATEGORIES: dict[str, tuple[str, str]] = {
    "Mobiles & Tablets":         ("1453", "mobile-phones_c339"),
    "Computers & Laptops":       ("1505", "computers-laptops_c1505"),
    "Electronics & Appliances":  ("1417", "electronics-appliances_c99"),
    "TVs & Audio":               ("1523", "tvs-video-audio-accessories_c99"),
    "Cameras & Lenses":          ("1517", "cameras-lenses_c99"),
    "Gaming":                    ("93",   "video-games-gaming_c99"),
    "Musical Instruments":       ("714",  "musical-instruments_c767"),
    "Sports & Fitness":          ("771",  "fitness-gym_c767"),
    "Cycles":                    ("1415", "cycles_c2198"),
    "Fashion":                   ("1793", "fashion_c87"),
    "Furniture & Home Decor":    ("1591", "furniture-home-decor_c628"),
    "Home Appliances":           ("1615", "home-appliances_c99"),
    "Books & Education":         ("453",  "books_c767"),
    "Kids & Baby":               ("235",  "kids_c87"),
    "Pets":                      ("139",  "pets_c103"),
    "Bikes & Motorcycles":       ("81",   "motorcycles_c2198"),
    "Cars":                      ("84",   "cars_c5"),
    "Health & Beauty":           ("741",  "health-beauty_c619"),
    "Art & Collectibles":        ("755",  "art-antiques-collectibles_c767"),
    "Toys & Games":              ("93",   "toys_c99"),
}


# ── Quikr Category Definitions ─────────────────────────────────────────────
# URL path segments for Quikr classifieds (city slug is appended)

QUIKR_CATEGORIES: dict[str, str] = {
    "Mobiles & Accessories":    "mobiles-and-accessories",
    "Electronics":              "electronics",
    "Furniture":                "furniture",
    "Cars":                     "cars",
    "Bikes & Motorcycles":      "bikes",
    "Fashion & Beauty":         "fashion-and-beauty",
    "Books & Education":        "education-books",
    "Sports & Fitness":         "sports-fitness",
    "Kids & Baby":              "kids-baby",
    "Cameras":                  "cameras",
    "Musical Instruments":      "musical-instruments",
    "Home Appliances":          "home-appliances",
    "Pets":                     "pets",
    "Gaming":                   "video-games",
    "Cycling":                  "cycling",
    "Art & Collectibles":       "art-antiques-collectibles",
}


def get_city(name: str) -> CityConfig:
    """Get city config by name (case-insensitive). Raises ValueError if unknown."""
    key = name.lower().strip()
    if key not in CITIES:
        available = ", ".join(sorted(CITIES.keys()))
        raise ValueError(f"Unknown city '{name}'. Available: {available}")
    return CITIES[key]


def list_cities() -> list[str]:
    """Return sorted list of supported city names."""
    return sorted(CITIES.keys())
