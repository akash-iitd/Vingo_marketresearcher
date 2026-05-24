"""
Quikr – City-aware category scraper.

Uses httpx + BeautifulSoup to scrape Quikr classifieds category pages.
Supports multiple cities via URL slug substitution.

URL pattern: https://www.quikr.com/{city-slug}/{category-slug}
Alternative: https://www.quikr.com/classifieds/{category-slug}/{city-slug}
"""

import re
import asyncio
import httpx
from bs4 import BeautifulSoup
from typing import Optional

from config import CityConfig, QUIKR_CATEGORIES

BASE_URL = "https://www.quikr.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _parse_count(text: str) -> int:
    """Extract a number from text like '2.5K results', '1,234 ads', etc."""
    text = text.strip().upper()
    m = re.search(r"([\d.]+)\s*K", text)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"([\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else 0


def _parse_quikr_age(s: str) -> Optional[float]:
    """Parse Quikr's relative date string into hours. Returns None if unparseable."""
    s = s.lower().strip()
    if "just now" in s or "today" in s:
        return 2
    if "yesterday" in s:
        return 24
    m = re.search(r"(\d+)\s*(min|hour|day|week|month)s?", s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    # Strip plural 's'
    unit = unit.rstrip('s')
    try:
        return {"min": n / 60, "hour": n, "day": n * 24, "week": n * 168, "month": n * 720}[unit]
    except KeyError:
        return None


def _get_quikr_url(category_name: str, city_slug: str) -> str:
    lifestyle_cats = [
        "Furniture", "Fashion & Beauty", "Books & Education", 
        "Sports & Fitness", "Kids & Baby", "Musical Instruments", 
        "Cycling", "Art & Collectibles"
    ]
    electronics_cats = [
        "Electronics", "Home Appliances", "Cameras", "Gaming"
    ]
    
    city_lower = city_slug.lower()
    city_title = city_slug.title()
    
    if category_name == "Mobiles & Accessories":
        return f"https://{city_lower}.quikr.com/mobiles-tablets/gId269"
    elif category_name in electronics_cats:
        if category_name == "Cameras":
            return f"https://www.quikr.com/electronics-appliances/Camera-Accessories+{city_title}+w18222208872f"
        elif category_name == "Home Appliances":
            return f"https://www.quikr.com/electronics-appliances/Refrigerators+{city_title}+w18408444f"
        else:
            return f"https://{city_lower}.quikr.com/electronics-appliances/gId247"
    elif category_name in lifestyle_cats:
        if category_name == "Furniture":
            return f"https://www.quikr.com/home-lifestyle/Used+Home-Office-Furniture+{city_title}+w218fm"
        else:
            return f"https://{city_lower}.quikr.com/home-lifestyle/gId40"
    elif category_name == "Cars":
        return f"https://www.quikr.com/cars/used+cars+{city_lower}+w1399"
    elif category_name == "Bikes & Motorcycles":
        return f"https://www.quikr.com/bikes-scooters/used+bikes-scooters+{city_lower}+w1402"
    elif category_name == "Pets":
        return f"https://www.quikr.com/pets/{city_lower}"
    else:
        return f"https://{city_lower}.quikr.com/home-lifestyle/gId40" # Fallback


async def _scrape_category(
    client: httpx.AsyncClient, name: str, category_slug: str, city: CityConfig
) -> dict:
    """Scrape a single Quikr category page for a city."""
    url = _get_quikr_url(name, city.quikr_slug)

    result = {
        "source": "Quikr",
        "category": name,
        "city": city.display_name,
        "url": url,
        "total_listings": 0,
        "listings_24h": 0,
        "listings_7d": 0,
        "sample_size": 0,
        "freshness_24h_pct": 0.0,
        "freshness_7d_pct": 0.0,
        "error": None,
    }

    try:
        resp = await client.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        if resp.status_code == 200 and "404error" not in resp.url.path.lower():
            soup = BeautifulSoup(resp.text, "lxml")
            result["url"] = str(resp.url)

            # ── Extract distinct listing cards ──────────────────────────────────
            cards = [a for a in soup.find_all("a", href=True) if "/p/" in a["href"]]
            distinct_cards = list(set(c["href"] for c in cards))
            
            # Estimate total listings (typical search result has ~10 pages)
            result["total_listings"] = len(distinct_cards) * 10

            # ── Extract timestamps ──────────────────────────────────────────
            ages = []
            for sel in [
                ".posted-date", "time", "[class*='date']",
                "[class*='time']", ".age", "[class*='posted']",
                "li", "span", "div"
            ]:
                for el in soup.select(sel):
                    txt = el.get_text().strip()
                    if len(txt) < 30:
                        h = _parse_quikr_age(txt)
                        if h is not None:
                            ages.append(h)
                if ages:
                    break

            result["sample_size"] = len(ages)
            if ages:
                result["listings_24h"] = sum(1 for h in ages if h <= 24)
                result["listings_7d"] = sum(1 for h in ages if h <= 168)
                result["freshness_24h_pct"] = round(
                    result["listings_24h"] / len(ages) * 100, 1
                )
                result["freshness_7d_pct"] = round(
                    result["listings_7d"] / len(ages) * 100, 1
                )

        else:
            result["error"] = f"HTTP {resp.status_code}"

    except httpx.TimeoutException:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:120]

    if result["total_listings"] == 0 and not result["error"]:
        result["error"] = "No listing data found (page structure may have changed)"

    return result


async def scrape_quikr(
    city: CityConfig,
    categories: Optional[dict] = None,
    quick: bool = False,
) -> list[dict]:
    """
    Scrape Quikr categories for a given city.

    Args:
        city: CityConfig with the Quikr city slug
        categories: dict of {name: slug} — defaults to all categories
        quick: only scrape first 5 categories
    """
    cats = categories or QUIKR_CATEGORIES
    if quick:
        cats = dict(list(cats.items())[:5])

    results = []
    async with httpx.AsyncClient() as client:
        items = list(cats.items())
        for i in range(0, len(items), 4):
            batch = items[i : i + 4]
            tasks = [
                _scrape_category(client, name, slug, city)
                for name, slug in batch
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)

            scraped = min(i + 4, len(items))
            ok = sum(1 for r in batch_results if not r.get("error"))
            print(f"  Quikr [{scraped}/{len(items)}] — {ok}/{len(batch)} OK")
            await asyncio.sleep(1.5)

    return results
