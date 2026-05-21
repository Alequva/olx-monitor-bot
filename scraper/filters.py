from urllib.parse import urlencode

BASE_LISTING_URL = "https://www.olx.uz/nedvizhimost/kvartiry"

CATEGORY_MAP = {
    "arenda-dolgosrochnaya": "arenda-dolgosrochnaya",
    "rent": "arenda-dolgosrochnaya",
    "prodazha": "prodazha",
    "sale": "prodazha",
    "komnaty": "komnaty",
    "rooms": "komnaty",
}

ROOMS_MAP = {
    "1": "odnokomnatnye",
    "2": "dvuhkomnatnye",
    "3": "trehkomnatnye",
    "4+": "chetyre-i-bolee-komnat",
}


def build_search_url(
    category: str = "arenda-dolgosrochnaya",
    price_min: int = 0,
    price_max: int = 0,
    location: str = "",
    rooms: str = "",
    page: int = 1,
) -> str:
    cat_slug = CATEGORY_MAP.get(category, category)
    base = f"{BASE_LISTING_URL}/{cat_slug}/"

    params = {}

    if price_min > 0:
        params["search[filter_float_price:from]"] = str(price_min)
    if price_max > 0:
        params["search[filter_float_price:to]"] = str(price_max)

    params["search[order]"] = "created_at:desc"

    if rooms:
        room_slug = ROOMS_MAP.get(rooms, rooms)
        params["search[filter_enum_rooms][0]"] = room_slug

    params["page"] = str(page)

    if params:
        base += "?" + urlencode(params, doseq=True)
    return base


def is_ad_within_price(ad_price_uzs, ad_price_usd, price_min: int, price_max: int) -> bool:
    if price_min == 0 and price_max == 0:
        return True

    price = ad_price_usd if ad_price_usd else ad_price_uzs
    if price is None:
        return price_min == 0

    if price_min > 0 and price < price_min:
        return False
    if price_max > 0 and price > price_max:
        return False
    return True


def location_matches(ad_location: str, filter_location: str) -> bool:
    if not filter_location:
        return True
    return filter_location.lower() in ad_location.lower()
