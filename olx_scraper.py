"""
OLX India – Category scraper using internal search API.

Uses the OLX internal API at /api/relevance/v4/search to fetch
listing data per category and city. This is much more reliable than
the previous HTML-regex approach which returned identical data for
all categories.

Each API call returns:
  - data[]: array of individual listings with created_at timestamps
  - metadata: contains total_ads count and pagination info

Usage: Called from main.py with a CityConfig and category dict.
"""

import asyncio
import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx
from curl_cffi.requests import AsyncSession

from config import CityConfig, OLX_CATEGORIES

IST = timezone(timedelta(hours=5, minutes=30))
BASE_API = "https://www.olx.in/api/relevance/v4/search"
CHECKPOINT_FILE = Path(__file__).parent.parent / "output" / "olx_checkpoint.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.olx.in/",
    "Connection": "keep-alive",
}


def _compute_freshness(dates: list[datetime]) -> dict:
    """Compute freshness metrics from listing timestamps."""
    now = datetime.now(IST)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    n = len(dates)
    if n == 0:
        return {
            "sample_size": 0,
            "listings_24h": 0,
            "listings_7d": 0,
            "freshness_24h_pct": 0.0,
            "freshness_7d_pct": 0.0,
        }

    f24 = sum(1 for d in dates if d >= cutoff_24h)
    f7d = sum(1 for d in dates if d >= cutoff_7d)
    return {
        "sample_size": n,
        "listings_24h": f24,
        "listings_7d": f7d,
        "freshness_24h_pct": round(f24 / n * 100, 1),
        "freshness_7d_pct": round(f7d / n * 100, 1),
    }


def _parse_api_response(data: dict, name: str, city: CityConfig) -> dict:
    """Parse the OLX API JSON response into our standard record format."""
    result = {
        "source": "OLX",
        "category": name,
        "city": city.display_name,
        "total_listings": 0,
        "sample_size": 0,
        "listings_24h": 0,
        "listings_7d": 0,
        "freshness_24h_pct": 0.0,
        "freshness_7d_pct": 0.0,
        "error": None,
    }

    listings = data.get("data", [])
    metadata = data.get("metadata", {})

    # Get total count from metadata or fall back to listing count
    total = metadata.get("total_ads", metadata.get("total", len(listings)))
    result["total_listings"] = int(total) if total else len(listings)

    # Extract timestamps from each listing
    dates = []
    for item in listings:
        created = item.get("created_at") or item.get("created_at_first")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=IST)
                dates.append(dt)
            except (ValueError, TypeError):
                continue

    freshness = _compute_freshness(dates)
    result.update(freshness)

    return result


async def _scrape_category(
    session: AsyncSession,
    name: str,
    cat_id: str,
    city: CityConfig,
    delay: float,
    page_limit: int = 3,
) -> dict:
    """Scrape a single OLX category using the search API.

    Fetches multiple pages to get a good sample of listing timestamps.
    """
    result = {
        "source": "OLX",
        "category": name,
        "city": city.display_name,
        "total_listings": 0,
        "sample_size": 0,
        "listings_24h": 0,
        "listings_7d": 0,
        "freshness_24h_pct": 0.0,
        "freshness_7d_pct": 0.0,
        "error": None,
    }

    all_dates = []
    total_from_api = 0

    for page in range(1, page_limit + 1):
        await asyncio.sleep(delay + random.uniform(0.5, 2.0))

        params = {
            "location": city.olx_location_id,
            "category": cat_id,
            "page": page,
            "limit": 40,
            "lang": "en-IN",
        }

        try:
            resp = await session.get(
                BASE_API,
                params=params,
                headers=_HEADERS,
                timeout=30,
            )

            if resp.status_code == 429:
                result["error"] = "Rate limited"
                break
            if resp.status_code != 200:
                result["error"] = f"HTTP {resp.status_code}"
                break

            data = resp.json()
            listings = data.get("data", [])

            if not listings:
                break  # No more results

            # Get total from first page metadata
            if page == 1:
                metadata = data.get("metadata", {})
                total_from_api = metadata.get(
                    "total_ads", metadata.get("total", 0)
                )

            # Extract dates from listings
            for item in listings:
                created = item.get("created_at") or item.get("created_at_first")
                if created:
                    try:
                        dt = datetime.fromisoformat(created)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=IST)
                        all_dates.append(dt)
                    except (ValueError, TypeError):
                        continue

        except Exception as e:
            err_str = str(e).lower()
            if "timeout" in err_str or "timed out" in err_str:
                result["error"] = f"Timeout on page {page}"
            else:
                result["error"] = str(e)[:120]
            break

    # Compute final metrics
    result["total_listings"] = int(total_from_api) if total_from_api else len(all_dates)
    freshness = _compute_freshness(all_dates)
    result.update(freshness)

    return result


def _load_checkpoint(city_slug: str) -> dict:
    checkpoint_file = Path(__file__).parent.parent / "output" / f"olx_checkpoint_{city_slug}.json"
    if checkpoint_file.exists():
        try:
            return json.loads(checkpoint_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_checkpoint(done: dict, city_slug: str) -> None:
    checkpoint_file = Path(__file__).parent.parent / "output" / f"olx_checkpoint_{city_slug}.json"
    checkpoint_file.parent.mkdir(exist_ok=True)
    checkpoint_file.write_text(json.dumps(done, indent=2, default=str), encoding="utf-8")


async def scrape_olx(
    city: CityConfig,
    categories: Optional[dict] = None,
    resume: bool = True,
    quick: bool = False,
) -> list[dict]:
    """
    Scrape OLX categories for a given city using the internal API.

    Args:
        city: CityConfig with the OLX location ID
        categories: dict of {name: (cat_id, slug)} — defaults to all categories
        resume: skip already-scraped categories from checkpoint
        quick: only scrape first 5 categories (for testing)
    """
    cats = categories or OLX_CATEGORIES
    if quick:
        cats = dict(list(cats.items())[:5])

    checkpoint = _load_checkpoint(city.name) if resume else {}
    delay = 2.0  # API is more tolerant than HTML scraping

    results = []
    # Restore already-done results from checkpoint
    for name in list(cats.keys()):
        if name in checkpoint:
            results.append(checkpoint[name])

    remaining = [(n, v) for n, v in cats.items() if n not in checkpoint]
    if not remaining:
        print(f"  OLX: all categories loaded from checkpoint ({city.display_name})")
        return results

    async with AsyncSession(impersonate="chrome124") as session:
        print(f"  Connecting to OLX API for {city.display_name}...")

        for i, (name, (cat_id, slug)) in enumerate(remaining):
            # Fetch up to 3 pages for good sample, 1 page in quick mode
            page_limit = 1 if quick else 3
            result = await _scrape_category(
                session, name, cat_id, city, delay, page_limit
            )
            results.append(result)

            # Persist incremental progress
            checkpoint[name] = result
            _save_checkpoint(checkpoint, city.name)

            status = (
                f"total={result['total_listings']:,} | "
                f"7d={result['freshness_7d_pct']:.0f}% | "
                f"24h={result['freshness_24h_pct']:.0f}%"
            )
            err = f" ! {result['error']}" if result.get("error") else ""
            done = len(checkpoint)
            total = len(cats)
            print(f"  OLX [{done}/{total}] {name}: {status}{err}")

    return results
