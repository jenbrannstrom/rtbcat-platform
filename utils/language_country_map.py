"""Language to country mapping for geo-mismatch detection.

Maps ISO 639-1 language codes to ISO 3166-1 alpha-2 country codes
where the language is an official or widely spoken language.
"""

from typing import Optional

# Map of ISO 639-1 language codes to countries where language is official/common
# Using ISO 3166-1 alpha-2 country codes
LANGUAGE_TO_COUNTRIES: dict[str, list[str]] = {
    # English - major English-speaking countries
    "en": ["US", "GB", "CA", "AU", "NZ", "IE", "ZA", "SG", "IN", "PH", "NG", "KE", "GH"],

    # German - DACH region
    "de": ["DE", "AT", "CH", "LI", "LU", "BE"],

    # French - Francophone countries
    "fr": ["FR", "BE", "CH", "CA", "LU", "MC", "SN", "CI", "ML", "BF", "NE", "TG", "BJ", "MG"],

    # Spanish - Hispanic countries
    "es": ["ES", "MX", "AR", "CO", "PE", "VE", "CL", "EC", "GT", "CU", "DO", "BO", "HN", "PY", "SV", "NI", "CR", "PA", "UY", "PR"],

    # Italian
    "it": ["IT", "CH", "SM", "VA"],

    # Portuguese
    "pt": ["PT", "BR", "AO", "MZ", "CV", "GW", "ST", "TL", "MO"],

    # Dutch
    "nl": ["NL", "BE", "SR", "CW", "AW", "SX"],

    # Polish
    "pl": ["PL"],

    # Russian
    "ru": ["RU", "BY", "KZ", "KG"],

    # Japanese
    "ja": ["JP"],

    # Korean
    "ko": ["KR", "KP"],

    # Chinese (Simplified/Traditional)
    "zh": ["CN", "TW", "HK", "MO", "SG"],

    # Arabic
    "ar": ["SA", "EG", "AE", "IQ", "JO", "KW", "LB", "LY", "MA", "OM", "QA", "SD", "SY", "TN", "YE", "DZ", "BH"],

    # Hindi
    "hi": ["IN"],

    # Turkish
    "tr": ["TR", "CY"],

    # Thai
    "th": ["TH"],

    # Vietnamese
    "vi": ["VN"],

    # Indonesian
    "id": ["ID"],

    # Malay
    "ms": ["MY", "SG", "BN"],

    # Swedish
    "sv": ["SE", "FI"],

    # Danish
    "da": ["DK", "GL", "FO"],

    # Norwegian
    "no": ["NO"],

    # Finnish
    "fi": ["FI"],

    # Czech
    "cs": ["CZ"],

    # Greek
    "el": ["GR", "CY"],

    # Hebrew
    "he": ["IL"],

    # Hungarian
    "hu": ["HU"],

    # Romanian
    "ro": ["RO", "MD"],

    # Ukrainian
    "uk": ["UA"],

    # Bulgarian
    "bg": ["BG"],

    # Croatian
    "hr": ["HR", "BA"],

    # Serbian
    "sr": ["RS", "BA", "ME"],

    # Slovak
    "sk": ["SK"],

    # Slovenian
    "sl": ["SI"],

    # Estonian
    "et": ["EE"],

    # Latvian
    "lv": ["LV"],

    # Lithuanian
    "lt": ["LT"],

    # Bengali
    "bn": ["BD", "IN"],

    # Tamil
    "ta": ["IN", "LK", "SG", "MY"],

    # Telugu
    "te": ["IN"],

    # Marathi
    "mr": ["IN"],

    # Urdu
    "ur": ["PK", "IN"],

    # Swahili
    "sw": ["KE", "TZ", "UG"],
}

# Reverse mapping: country to primary languages
COUNTRY_TO_LANGUAGES: dict[str, list[str]] = {}
for lang, countries in LANGUAGE_TO_COUNTRIES.items():
    for country in countries:
        if country not in COUNTRY_TO_LANGUAGES:
            COUNTRY_TO_LANGUAGES[country] = []
        COUNTRY_TO_LANGUAGES[country].append(lang)


def get_countries_for_language(language_code: str) -> list[str]:
    """Get list of country codes where a language is commonly spoken.

    Args:
        language_code: ISO 639-1 language code (e.g., "de", "fr")

    Returns:
        List of ISO 3166-1 alpha-2 country codes
    """
    if not language_code:
        return []
    return LANGUAGE_TO_COUNTRIES.get(language_code.lower(), [])


def get_languages_for_country(country_code: str) -> list[str]:
    """Get list of language codes commonly spoken in a country.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., "DE", "FR")

    Returns:
        List of ISO 639-1 language codes
    """
    if not country_code:
        return []
    return COUNTRY_TO_LANGUAGES.get(country_code.upper(), [])


def check_language_country_match(
    language_code: str,
    country_codes: list[str],
) -> dict:
    """Check if a language matches the serving countries.

    Args:
        language_code: ISO 639-1 language code of the creative content
        country_codes: List of ISO 3166-1 alpha-2 country codes where creative is serving

    Returns:
        Dict with:
            - is_match: True if language matches at least one serving country
            - matching_countries: List of countries where language matches
            - mismatched_countries: List of countries where language doesn't match
            - expected_countries: List of countries where this language is expected
    """
    if not language_code or not country_codes:
        return {
            "is_match": True,  # No mismatch if we can't determine
            "matching_countries": [],
            "mismatched_countries": [],
            "expected_countries": [],
        }

    expected_countries = set(get_countries_for_language(language_code))
    serving_countries = set(c.upper() for c in country_codes)

    matching = expected_countries & serving_countries
    mismatched = serving_countries - expected_countries

    return {
        "is_match": len(matching) > 0 or len(mismatched) == 0,
        "matching_countries": sorted(list(matching)),
        "mismatched_countries": sorted(list(mismatched)),
        "expected_countries": sorted(list(expected_countries)),
    }


def get_mismatch_alert(
    language_code: str,
    language_name: str,
    serving_countries: list[str],
) -> Optional[dict]:
    """Generate a geo-mismatch alert if language doesn't match serving countries.

    Args:
        language_code: ISO 639-1 language code
        language_name: Human-readable language name
        serving_countries: List of country codes where creative is serving

    Returns:
        Alert dict if mismatch detected, None otherwise
    """
    if not language_code or not serving_countries:
        return None

    result = check_language_country_match(language_code, serving_countries)

    # No alert if language matches at least one serving country.
    # Mixed serving (e.g. English creative in US + Brazil) is normal — the
    # creative matches the US audience, Brazil is just additional reach.
    if result["is_match"]:
        return None

    # Only alert when creative language matches NONE of the serving countries.
    mismatched = result["mismatched_countries"]
    expected = result["expected_countries"]

    if not mismatched:
        return None

    # Import here to avoid circular imports
    from utils.country_codes import get_country_name

    mismatched_names = [get_country_name(c) for c in mismatched[:3]]
    expected_names = [get_country_name(c) for c in expected[:3]]

    return {
        "severity": "warning",
        "language": language_name,
        "language_code": language_code,
        "mismatched_countries": mismatched,
        "expected_countries": expected,
        "message": (
            f"Creative content is in {language_name}, "
            f"but serving in {', '.join(mismatched_names)}. "
            f"{language_name} is typically used in {', '.join(expected_names)}."
        ),
    }
