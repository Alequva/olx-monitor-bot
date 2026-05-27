import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.olx.uz"

RUSSIAN_MONTHS = {
    "января": "01", "февраля": "02", "марта": "03",
    "апреля": "04", "мая": "05", "июня": "06",
    "июля": "07", "августа": "08", "сентября": "09",
    "октября": "10", "ноября": "11", "декабря": "12",
}

RUSSIAN_MONTHS_NOM = {
    "январь": "01", "февраль": "02", "март": "03",
    "апрель": "04", "май": "05", "июнь": "06",
    "июль": "07", "август": "08", "сентябрь": "09",
    "октябрь": "10", "ноябрь": "11", "декабрь": "12",
}


class ParsedAd:
    def __init__(
        self,
        title: str,
        price_uzs: Optional[float],
        price_usd: Optional[float],
        date: datetime,
        location: str,
        image_url: Optional[str],
        post_url: str,
        description: str = "",
        phone: str = "",
        preferred_phone: str = "",
    ):
        self.title = title
        self.price_uzs = price_uzs
        self.price_usd = price_usd
        self.date = date
        self.location = location
        self.image_url = image_url
        self.post_url = post_url
        self.description = description
        self.phone = phone
        self.preferred_phone = preferred_phone

    @property
    def days_ago(self) -> str:
        delta = datetime.now(timezone.utc) - self.date
        if delta.days == 0:
            return "today"
        if delta.days == 1:
            return "yesterday"
        return f"{delta.days} days ago"

    @property
    def formatted_date(self) -> str:
        return self.date.strftime("%d %b %Y at %H:%M")


def parse_card(card: Tag) -> Optional[ParsedAd]:
    try:
        post_url = _find_post_url(card)
        if not post_url:
            return None

        title = _find_title(card)
        image_url = _find_image(card)
        price_uzs, price_usd = _find_price(card)
        location, date_str = _find_location_and_date(card)
        date = _parse_date_str(date_str)
        description = _find_description(card, title)

        return ParsedAd(
            title=title,
            price_uzs=price_uzs,
            price_usd=price_usd,
            date=date,
            location=location,
            image_url=image_url,
            post_url=post_url,
            description=description,
        )
    except Exception:
        return None


def _find_post_url(card: Tag) -> Optional[str]:
    for a in card.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/d/obyavlenie/") or "/d/obyavlenie/" in href:
            return urljoin(BASE_URL, href)
        if href.startswith("https://www.olx.uz/d/obyavlenie/"):
            return href
    a = card.find("a", href=True)
    if a:
        href = a["href"]
        return urljoin(BASE_URL, href) if not href.startswith("http") else href
    return None


def _find_title(card: Tag) -> str:
    h4 = card.find("h4")
    if h4:
        return h4.get_text(strip=True)

    title_div = card.find("div", attrs={"data-cy": "ad-card-title"})
    if title_div:
        return title_div.get_text(strip=True)

    for a in card.find_all("a", href=True):
        if a.get_text(strip=True):
            return a.get_text(strip=True)
    return ""


def _find_image(card: Tag) -> Optional[str]:
    for img in card.find_all("img"):
        src = img.get("src") or img.get("data-src", "")
        if src.startswith("http"):
            return src
    return None


def _find_price(card: Tag) -> tuple[Optional[float], Optional[float]]:
    p = card.find("p", class_="css-blr5zl")
    if p:
        text = p.get_text(strip=True)
        return _parse_price(text)

    for tag in card.find_all(["p", "h3", "span"]):
        text = tag.get_text(strip=True)
        if "сум" in text or "у.е." in text:
            return _parse_price(text)
    return None, None


def _find_location_and_date(card: Tag) -> tuple[str, str]:
    p = card.find("p", class_="css-1b24pxk")
    if p:
        text = p.get_text(strip=True)
        parts = text.split(" - ", 1)
        location = parts[0].strip() if parts else ""
        date_str = parts[1].strip() if len(parts) > 1 else text
        return location, date_str

    for tag in card.find_all(["p", "span"]):
        text = tag.get_text(strip=True)
        if " - " in text and any(
            kw in text for kw in
            ["сегодня", "вчера", "января", "февраля", "марта",
             "апреля", "мая", "июня", "июля", "августа",
             "сентября", "октября", "ноября", "декабря"]
        ):
            parts = text.split(" - ", 1)
            location = parts[0].strip()
            date_str = parts[1].strip() if len(parts) > 1 else text
            return location, date_str
    return "", ""


def _find_description(card: Tag, title: str) -> str:
    h4 = card.find("h4")
    if h4:
        for sibling in h4.find_next_siblings():
            text = sibling.get_text(strip=True)
            if len(text) > 3 and text != title:
                class_names = sibling.get("class", [])
                cn = " ".join(str(c) for c in class_names)
                if "css-blr5zl" in cn or "css-1b24pxk" in cn:
                    continue
                return text
    return ""


def _parse_price(text: str) -> tuple[Optional[float], Optional[float]]:
    text = text.replace("\xa0", " ")

    summ_match = re.search(r"([\d\s]+)\s*сум", text)
    if summ_match:
        raw = summ_match.group(1).replace(" ", "").replace("\xa0", "")
        try:
            val = float(raw)
            usd = round(val / 12000, 2)
            return val, usd
        except ValueError:
            pass

    if "у.е." in text or "$" in text:
        num_match = re.search(r"([\d\s,.]+)", text.replace(" ", ""))
        if num_match:
            raw = num_match.group(1).replace(",", ".").strip()
            try:
                val = float(raw)
                return None, val
            except ValueError:
                pass

    nums = re.findall(r"[\d\s]+", text.replace(" ", ""))
    if nums and nums[0].strip():
        try:
            val = float(nums[0].strip())
            return val, None
        except ValueError:
            pass
    return None, None


PHONE_PATTERN = re.compile(
    r'(?:\+998|8)[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'
)


def extract_phones_from_text(text: str) -> list[str]:
    if not text:
        return []
    raw = PHONE_PATTERN.findall(text)
    seen = set()
    result = []
    for match in raw:
        phone = normalize_phone(match)
        if phone and phone not in seen:
            seen.add(phone)
            result.append(phone)
    return result


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r'\D', '', raw)
    if digits.startswith('8') and len(digits) == 11:
        digits = '998' + digits[1:]
    elif digits.startswith('998') and len(digits) == 12:
        pass
    else:
        return None
    return '+' + digits


def format_phone(phone: str) -> str:
    if len(phone) == 13 and phone.startswith('+998'):
        return f"{phone[:4]} {phone[4:6]} {phone[6:9]} {phone[9:11]} {phone[11:]}"
    return phone


def _parse_date_str(date_str: str) -> datetime:
    now = datetime.now(timezone.utc)
    if not date_str:
        return now

    date_str = date_str.strip().lower()

    if date_str.startswith("сегодня"):
        time_part = _extract_time(date_str)
        return now.replace(
            hour=time_part[0], minute=time_part[1],
            second=0, microsecond=0
        )

    if date_str.startswith("вчера"):
        time_part = _extract_time(date_str)
        yesterday = now - timedelta(days=1)
        return yesterday.replace(
            hour=time_part[0], minute=time_part[1],
            second=0, microsecond=0
        )

    parsed = _parse_russian_date(date_str)
    if parsed:
        return parsed

    return now


def _extract_time(text: str) -> tuple[int, int]:
    match = re.search(r"(\d{1,2}):(\d{2})", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _parse_russian_date(text: str) -> Optional[datetime]:
    now = datetime.now(timezone.utc)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" г.", "")

    for ru_month, num_month in {**RUSSIAN_MONTHS, **RUSSIAN_MONTHS_NOM}.items():
        if ru_month in text:
            try:
                day_match = re.search(r"(\d{1,2})", text)
                year_match = re.search(r"(\d{4})", text)
                day = int(day_match.group(1)) if day_match else now.day
                year = int(year_match.group(1)) if year_match else now.year
                return datetime(year, int(num_month), day, tzinfo=timezone.utc)
            except ValueError:
                return None
    return None


def parse_listing_page(html: str) -> list[ParsedAd]:
    soup = BeautifulSoup(html, "lxml")
    ads = []
    cards = soup.find_all("div", attrs={"data-cy": "l-card"})
    for card in cards:
        parsed = parse_card(card)
        if parsed:
            ads.append(parsed)
    return ads


def has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    next_btn = soup.find("a", attrs={"data-cy": "pagination-forward"})
    if next_btn and not next_btn.get("disabled"):
        return True
    return False
