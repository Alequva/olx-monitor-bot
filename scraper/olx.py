import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config import SCRAPER_DELAY, USER_AGENT
from scraper.parser import (
    parse_listing_page, has_next_page, ParsedAd,
    extract_phones_from_text,
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
        # Second gender pass with full page text
        if gender_pref != "any":
            results = [
                ad for ad in results
                if gender_matches(ad.title, f"{ad.description} {ad.full_text}", gender_pref)
            ]

    return results


async def _attach_phones(ads: list[ParsedAd]):
    sem = asyncio.Semaphore(3)

    async def fetch(ad):
        html = await fetch_page(ad.post_url)
        page_text = ""
        if html:
            soup = BeautifulSoup(html, "lxml")
            page_text = soup.get_text(separator=" ", strip=True)
        ad.full_text = page_text

        combined = f"{ad.description} {page_text}"
        all_phones = extract_phones_from_text(combined)
        if all_phones:
            ad.phone = all_phones[0]
            if len(all_phones) > 1:
                ad.preferred_phone = all_phones[1]

    async def throttled_fetch(ad):
        async with sem:
            await fetch(ad)
            await asyncio.sleep(SCRAPER_DELAY)

    await asyncio.gather(*[throttled_fetch(ad) for ad in ads])


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
