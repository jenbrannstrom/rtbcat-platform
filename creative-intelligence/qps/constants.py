"""Constants for QPS Optimization.

Contains Google's available pretargeting sizes and billing ID configurations.
"""

# Google's 98 available sizes for pretargeting INCLUDE lists
# These are the ONLY sizes that can be filtered in pretargeting
GOOGLE_AVAILABLE_SIZES = frozenset([
    "468x60", "728x90", "250x250", "200x200", "336x280", "300x250", "120x600",
    "160x600", "320x50", "300x50", "425x600", "300x600", "970x90", "240x400",
    "980x120", "930x180", "250x360", "580x400", "300x1050", "480x320", "320x480",
    "768x1024", "1024x768", "480x32", "1024x90", "970x250", "300x100", "750x300",
    "750x200", "750x100", "950x90", "88x31", "220x90", "300x31", "320x100",
    "980x90", "240x133", "200x446", "292x30", "960x90", "970x66", "300x57",
    "120x60", "375x50", "414x736", "736x414", "320x400", "600x314", "400x400",
    "480x800", "500x500", "500x720", "600x500", "672x560", "1160x800", "600x100",
    "640x100", "640x200", "240x1200", "320x1200", "600x1200", "600x2100", "936x120",
    "1456x180", "1860x360", "1940x180", "1940x500", "1960x240", "850x1200",
    "960x640", "640x960", "1536x2048", "2048x1536", "960x64", "2048x180", "600x200",
    "1500x600", "1500x400", "1500x200", "1900x180", "176x62", "440x180", "600x62",
    "1960x180", "480x266", "400x892", "584x60", "1920x180", "1940x132", "600x114",
    "240x120", "828x1472", "1472x828", "640x800", "800x800", "960x1600", "1000x1000",
    "1000x1440", "1200x1000", "1344x1120", "2320x1600", "1200x200", "1280x200",
    "1280x400", "480x2400", "640x2400", "1200x2400", "1200x4200", "1872x240",
    "2912x360", "3720x720", "3880x360", "3880x1000", "3920x480",
])

# The 10 pretargeting configurations with billing IDs
PRETARGETING_CONFIGS = {
    "72245759413": {
        "name": "Africa/Asia Mix",
        "geos": ["BF", "BR", "CI", "CM", "EG", "NG", "SA", "SE", "IN", "PH", "KZ"],
        "budget_daily": 1200,
        "qps_limit": 50000,
    },
    "83435423204": {
        "name": "ID/BR Android",
        "geos": ["ID", "BR", "IN", "US", "KR", "ZA", "AR"],
        "platform": "Android",
        "budget_daily": 2000,
        "qps_limit": 50000,
    },
    "104602012074": {
        "name": "MENA iOS&AND",
        "geos": ["SA", "AE", "EG", "PH", "IT", "ES", "BF", "KZ", "FR", "PE", "ZA", "HU", "SK"],
        "budget_daily": 1200,
        "qps_limit": 50000,
    },
    "137175951277": {
        "name": "SEA Whitelist",
        "geos": ["BR", "ID", "MY", "TH", "VN"],
        "budget_daily": 1200,
        "qps_limit": 30000,
    },
    "151274651962": {
        "name": "USEast CA/MX",
        "geos": ["CA", "MX"],
        "budget_daily": 1500,
        "qps_limit": 5000,
    },
    "153322387893": {
        "name": "Brazil Android",
        "geos": ["BR"],
        "platform": "Android",
        "budget_daily": 1500,
        "qps_limit": 30000,
    },
    "155546863666": {
        "name": "Asia BL2003",
        "geos": ["ID", "IN", "TH", "CN", "KR", "TR", "VN", "BD", "PH", "MY"],
        "budget_daily": 1800,
        "qps_limit": 50000,
    },
    "156494841242": {
        "name": "Nova WL",
        "geos": ["JP", "BR"],
        "budget_daily": 2000,
        "qps_limit": 30000,
    },
    "157331516553": {
        "name": "US/Global",
        "geos": ["US", "PH", "AU", "KR", "EG", "PK", "BD", "UZ", "SA", "JP", "PE", "ZA", "HU", "SK", "AR", "KW"],
        "budget_daily": 3000,
        "qps_limit": 50000,
    },
    "158323666240": {
        "name": "BR/PH Spotify",
        "geos": ["BR", "PH"],
        "apps": ["com.spotify.music"],
        "budget_daily": 2000,
        "qps_limit": 30000,
    },
}

# Endpoint configuration (the real QPS bottleneck)
ENDPOINTS = {
    "us_west": {
        "url": "bidder.novabeyond.com",
        "qps_limit": 10000,
        "location": "US West",
    },
    "asia": {
        "url": "bidder-sg.novabeyond.com",
        "qps_limit": 30000,
        "location": "Asia",
    },
    "us_east": {
        "url": "bidder-us.novabeyond.com",
        "qps_limit": 50000,
        "location": "US East",
    },
}

# Total endpoint capacity (this is the REAL bottleneck, not pretargeting QPS)
TOTAL_ENDPOINT_QPS = sum(e["qps_limit"] for e in ENDPOINTS.values())  # 90,000

# Account info
ACCOUNT_ID = "299038253"
ACCOUNT_NAME = "Tuky Data Research Ltd."
