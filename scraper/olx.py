import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import SCRAPER_DELAY, USER_AGENT
from scraper.parser import (
    parse_listing_page, has_next_page, ParsedAd,
    extract_phones_from_text, normalize_phone, format_phone,
)
from scraper.filters import build_search_url, is_ad_within_price, location_matches, gender_matches


async def fetch_page(url: str) -> Optional[str]:
    headers = {"User-Agent": USER_AGENT}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.text
    except httpx.HTTPError:
        return None


async def scrape_listings(
    category: str,
    price_min: int = 0,
    price_max: int = 0,
    location: str = "",
    rooms: str = "",
    max_pages: int = 1,
    backlog_days: int = 7,
    gender_pref: str = "any",
) -> list[ParsedAd]:
    since = datetime.now(timezone.utc) - timedelta(days=backlog_days)
    results = []

    for page in range(1, max_pages + 1):
        url = build_search_url(category=category, page=page)

        html = await fetch_page(url)
        if not html:
            break

        ads = parse_listing_page(html)
        if not ads:
            break

        page_stale = True
        for ad in ads:
            if ad.date >= since - timedelta(days=1):
                page_stale = False

            if ad.date < since:
                continue

            if not is_ad_within_price(ad.price_uzs, ad.price_usd, price_min, price_max):
                continue
            if not location_matches(ad.location, location):
                continue
            if not gender_matches(ad.title, ad.description, gender_pref):
                continue

            results.append(ad)

        if page_stale:
            break

        if not has_next_page(html):
            break

        await asyncio.sleep(SCRAPER_DELAY)

    if results:
        await _attach_phones(results)

    return results


def _extract_offer_id(url: str) -> str | None:
    match = re.search(r'[.\-](\d+)\.html', url)
    return match.group(1) if match else None


async def _fetch_phone_via_api(offer_id: str, referer: str) -> str | None:
    url = f"https://www.olx.uz/api/v1/offers/{offer_id}/phone/"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": referer,
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("phone", "")
    except Exception:
        pass
    return None


def _extract_phone_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    el = soup.find("a", attrs={"data-testid": "contact-phone"})
    if el:
        href = el.get("href", "")
        if href.startswith("tel:"):
            return href[4:]
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("tel:"):
            return href[4:]
    phones = extract_phones_from_text(soup.get_text())
    if phones:
        return phones[0]
    return None


async def fetch_phone_for_ad(post_url: str) -> str:
    offer_id = _extract_offer_id(post_url)
    raw = None
    if offer_id:
        raw = await _fetch_phone_via_api(offer_id, post_url)
    if not raw:
        html = await fetch_page(post_url)
        if html:
            raw = _extract_phone_from_html(html)
            if raw:
                raw = normalize_phone(raw)
    return raw or ""


async def _attach_phones(ads: list[ParsedAd]):
    async def fetch(ad):
        ad.phone = await fetch_phone_for_ad(ad.post_url)
        desc_phones = extract_phones_from_text(ad.description)
        if desc_phones:
            other = [p for p in desc_phones if p != ad.phone]
            if other:
                ad.preferred_phone = other[0]

    await asyncio.gather(*[fetch(ad) for ad in ads])


async def scrape_for_user(
    category: str,
    price_min: int = 0,
    price_max: int = 0,
    location: str = "",
    rooms: str = "",
    backlog_days: int = 7,
    gender_pref: str = "any",
    single_page: bool = False,
) -> list[ParsedAd]:
    max_pages = 1 if single_page else 50
    return await scrape_listings(
        category=category,
        price_min=price_min,
        price_max=price_max,
        location=location,
        rooms=rooms,
        max_pages=max_pages,
        backlog_days=backlog_days,
        gender_pref=gender_pref,
    )
