from urllib.parse import urlencode

BASE_LISTING_URL = "https://www.olx.uz/nedvizhimost/kvartiry"

CATEGORY_MAP = {
    "arenda-dolgosrochnaya": "arenda-dolgosrochnaya",
    "rent": "arenda-dolgosrochnaya",
    "prodazha": "prodazha",
    "sale": "prodazha",
    "komnaty": "q-комнаты",
    "rooms": "q-комнаты",
}

ROOMS_MAP = {
    "1": "odnokomnatnye",
    "2": "dvuhkomnatnye",
    "3": "trehkomnatnye",
    "4+": "chetyre-i-bolee-komnat",
}

SEARCH_CATEGORIES = {"q-комнаты"}


def build_search_url(category: str = "arenda-dolgosrochnaya", page: int = 1) -> str:
    cat_slug = CATEGORY_MAP.get(category, category)
    base = f"{BASE_LISTING_URL}/{cat_slug}/"

    params = {"search[order]": "created_at:desc", "page": str(page)}

    return base + "?" + urlencode(params, doseq=True)


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


CITY_ALIASES = {
    "tashkent": ["ташкент", "toshkent"],
    "toshkent": ["ташкент", "tashkent"],
    "samarkand": ["самарканд", "samarqand"],
    "samarqand": ["самарканд", "samarkand"],
    "bukhara": ["бухара", "buxoro", "buxara"],
    "buxoro": ["бухара", "bukhara", "buxara"],
    "fergana": ["фергана", "farg'ona", "fargona"],
    "namangan": ["наманган"],
    "andijan": ["андижан", "andijon"],
    "nukus": ["нукус"],
    "urgench": ["ургенч"],
    "navoi": ["навои", "navoiy"],
    "jizzakh": ["джизак", "jizzax"],
    "qarshi": ["карши"],
    "karshi": ["карши"],
    "termez": ["термез"],
    "gulistan": ["гулистан"],
    "kokand": ["коканд"],
}


import re

GENDER_PREFIXES_WOMEN = [
    "девуш", "девоч", "женщ",
    "киз", "айол", "аёл", "қиз", "хотин", "хоним",
    "qiz", "ayol", "xotin", "xonim",
]
GENDER_PREFIXES_MEN = [
    "мальч", "парен", "парн", "муж",
    "йигит", "эркак", "бола", "болла", "жаноб",
    "yigit", "erkak", "bola", "janob",
]


def gender_matches(ad_title: str, ad_description: str, user_pref: str) -> bool:
    if user_pref == "any":
        return True
    text = (ad_title + " " + ad_description).lower()

    def has_any(prefixes):
        return any(re.search(rf"(?<!\w){p}", text) for p in prefixes)

    women_only = has_any(GENDER_PREFIXES_WOMEN)
    men_only = has_any(GENDER_PREFIXES_MEN)

    if women_only and not men_only:
        return user_pref == "women"
    if men_only and not women_only:
        return user_pref == "men"
    return True


def location_matches(ad_location: str, filter_location: str) -> bool:
    if not filter_location:
        return True
    ad_lower = ad_location.lower()
    filter_lower = filter_location.lower()

    if filter_lower in ad_lower:
        return True

    aliases = CITY_ALIASES.get(filter_lower, [])
    for alias in aliases:
        if alias in ad_lower:
            return True

    return False
