#!/usr/bin/env python3
"""
Scrape/compile Indy Pass 2025-26 resort list and fuzzy-match against our resort database.

Sources:
- indyskipass.com/resorts/ (primary, JS-rendered so partially scraped)
- OnTheSnow buyer's guide (comprehensive text list)
- SAM Magazine, PeakRankings articles (new resort additions)

Output: backend/data/indy_pass_matches.json
"""

import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Resolve paths relative to the repo root
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
RESORTS_JSON = REPO_ROOT / "backend" / "data" / "resorts.json"
OUTPUT_JSON = REPO_ROOT / "backend" / "data" / "indy_pass_matches.json"

# ---------------------------------------------------------------------------
# Indy Pass 2025-26 resort list (compiled from multiple sources)
# Format: (name, state/province or region, country_code)
#
# Country codes match our resorts.json: US, CA, JP, AT, CH, FR, IT, DE, ES,
# SE, NO, SI, CZ, GB (Scotland/England), TR (Turkey), CL (Chile), NZ, AU
# ---------------------------------------------------------------------------

INDY_RESORTS = [
    # === ALASKA ===
    ("Arctic Valley", "AK", "US"),
    ("Eaglecrest", "AK", "US"),
    ("Hilltop Ski Area", "AK", "US"),
    ("Mt. Eyak", "AK", "US"),
    # === PACIFIC NORTHWEST (WA, OR) ===
    ("49 Degrees North", "WA", "US"),
    ("Bluewood", "WA", "US"),
    ("Hurricane Ridge", "WA", "US"),
    ("Leavenworth Ski Hill", "WA", "US"),
    ("Loup Loup Ski Bowl", "WA", "US"),
    ("Mission Ridge", "WA", "US"),
    ("White Pass", "WA", "US"),
    ("Cooper Spur Ski Area", "OR", "US"),
    ("Hoodoo", "OR", "US"),
    ("Mt. Hood Meadows", "OR", "US"),
    # === CALIFORNIA ===
    ("Bear Valley Mountain Resort", "CA", "US"),
    ("Bear Valley Adventure Company", "CA", "US"),
    ("China Peak", "CA", "US"),
    ("Dodge Ridge", "CA", "US"),
    ("Donner Ski Ranch", "CA", "US"),
    ("Mountain High", "CA", "US"),
    ("Mt. Shasta Ski Park", "CA", "US"),
    # === INTERMOUNTAIN WEST ===
    # Idaho
    ("Brundage Mountain Resort", "ID", "US"),
    ("Kelly Canyon", "ID", "US"),
    ("Little Ski Hill", "ID", "US"),
    ("Magic Mountain", "ID", "US"),
    ("Pomerelle", "ID", "US"),
    ("Silver Mountain", "ID", "US"),
    ("Soldier Mountain", "ID", "US"),
    ("Tamarack Resort", "ID", "US"),
    # Montana
    ("Blacktail Mountain", "MT", "US"),
    ("Lost Trail Powder Mountain", "MT", "US"),
    ("Montana Snowbowl", "MT", "US"),
    ("Red Lodge Mountain", "MT", "US"),
    # Utah
    ("Beaver Mountain", "UT", "US"),
    ("Cherry Peak", "UT", "US"),
    ("Eagle Point", "UT", "US"),
    # Colorado
    ("Cuchara Mountain Resort", "CO", "US"),
    ("Echo Mountain", "CO", "US"),
    ("Granby Ranch", "CO", "US"),
    ("Hoedown Hill", "CO", "US"),
    ("Howelsen Hill", "CO", "US"),
    ("Loveland", "CO", "US"),
    ("Powderhorn", "CO", "US"),
    ("Sunlight Mountain Resort", "CO", "US"),
    # Wyoming
    ("Antelope Butte", "WY", "US"),
    ("Meadowlark Ski Lodge", "WY", "US"),
    ("Sleeping Giant", "WY", "US"),
    ("Snow King Mountain", "WY", "US"),
    ("White Pine Ski Resort", "WY", "US"),
    # Arizona / New Mexico
    ("Sunrise Park Resort", "AZ", "US"),
    # === MIDWEST ===
    # Illinois
    ("Chestnut Mountain Resort", "IL", "US"),
    ("Snowstar", "IL", "US"),
    # Iowa
    ("Sundown Mountain", "IA", "US"),
    # Michigan
    ("Big Powderhorn Mountain", "MI", "US"),
    ("Caberfae Peaks", "MI", "US"),
    ("Crystal Mountain", "MI", "US"),
    ("Marquette Mountain", "MI", "US"),
    ("Mont Ripley", "MI", "US"),
    ("Mt. Holiday", "MI", "US"),
    ("Norway Mountain", "MI", "US"),
    ("Nub's Nob", "MI", "US"),
    ("Pine Mountain", "MI", "US"),
    ("Schuss Mountain at Shanty Creek", "MI", "US"),
    ("Snowriver Mountain Resort", "MI", "US"),
    ("Swiss Valley", "MI", "US"),
    ("Treetops Resort", "MI", "US"),
    # Minnesota
    ("Andes Tower Hills", "MN", "US"),
    ("Buck Hill", "MN", "US"),
    ("Detroit Mountain", "MN", "US"),
    ("Hyland Hills Ski Area", "MN", "US"),
    ("Lutsen Mountains", "MN", "US"),
    ("Mount Kato", "MN", "US"),
    ("Powder Ridge", "MN", "US"),
    ("Spirit Mountain", "MN", "US"),
    ("Steeplechase Ski Area", "MN", "US"),
    # North Dakota
    ("Bottineau Winter Park", "ND", "US"),
    ("Huff Hills", "ND", "US"),
    # South Dakota
    ("Great Bear Ski Valley", "SD", "US"),
    ("Terry Peak", "SD", "US"),
    # Wisconsin
    ("Bruce Mound", "WI", "US"),
    ("Christie Mountain", "WI", "US"),
    ("Crystal Ridge", "WI", "US"),
    ("Granite Peak", "WI", "US"),
    ("Little Switzerland", "WI", "US"),
    ("Mt. La Crosse", "WI", "US"),
    ("Nordic Mountain", "WI", "US"),
    ("Sunburst Ski and Snowboard", "WI", "US"),
    ("The Rock Snowpark", "WI", "US"),
    ("Trollhaugen", "WI", "US"),
    ("Tyrol Basin", "WI", "US"),
    # === EAST COAST ===
    # Connecticut
    ("Mohawk Mountain", "CT", "US"),
    # Maine
    ("Big Moose Mountain", "ME", "US"),
    ("Big Rock Mountain", "ME", "US"),
    ("Black Mountain of Maine", "ME", "US"),
    ("Camden Snow Bowl", "ME", "US"),
    ("Lost Valley", "ME", "US"),
    ("Mt. Abram", "ME", "US"),
    ("Saddleback Mountain", "ME", "US"),
    # Massachusetts
    ("Berkshire East Mountain Resort", "MA", "US"),
    ("Bousquet Mountain", "MA", "US"),
    # New Hampshire
    ("Black Mountain", "NH", "US"),
    ("Cannon Mountain", "NH", "US"),
    ("Dartmouth Skiway", "NH", "US"),
    ("King Pine", "NH", "US"),
    ("McIntyre Ski Area", "NH", "US"),
    ("Pats Peak", "NH", "US"),
    ("Ragged Mountain", "NH", "US"),
    ("Tenney Mountain", "NH", "US"),
    ("Waterville Valley", "NH", "US"),
    ("Whaleback Mountain", "NH", "US"),
    # New York
    ("Buffalo Ski Club", "NY", "US"),
    ("Catamount Mountain Resort", "NY", "US"),
    ("Cazenovia Ski Club", "NY", "US"),
    ("Dry Hill Ski Area", "NY", "US"),
    ("Greek Peak Mountain Resort", "NY", "US"),
    ("Hunt Hollow Ski Club", "NY", "US"),
    ("Maple Ski Ridge", "NY", "US"),
    ("Peek'n Peak Resort", "NY", "US"),
    ("Skaneateles Ski Club", "NY", "US"),
    ("Snow Ridge", "NY", "US"),
    ("Swain Resort", "NY", "US"),
    ("Titus Mountain", "NY", "US"),
    ("West Mountain", "NY", "US"),
    # Pennsylvania
    ("Bear Creek Mountain Resort", "PA", "US"),
    ("Blue Knob All Seasons Resort", "PA", "US"),
    ("Montage Mountain", "PA", "US"),
    ("Shawnee Mountain", "PA", "US"),
    ("Ski Big Bear", "PA", "US"),
    ("Ski Sawmill", "PA", "US"),
    ("Tussey Mountain", "PA", "US"),
    # Tennessee
    ("Ober Gatlinburg", "TN", "US"),
    # Virginia
    ("Bryce Resort", "VA", "US"),
    ("Massanutten", "VA", "US"),
    ("Wintergreen Resort", "VA", "US"),
    # North Carolina
    ("Cataloochee Ski Area", "NC", "US"),
    # West Virginia
    ("Canaan Valley Resort", "WV", "US"),
    ("Winterplace", "WV", "US"),
    # Vermont
    ("Bolton Valley Resort", "VT", "US"),
    ("Burke Mountain", "VT", "US"),
    ("Jay Peak", "VT", "US"),
    ("Magic Mountain", "VT", "US"),
    ("Middlebury Snow Bowl", "VT", "US"),
    ("Saskadena Six", "VT", "US"),
    # === CANADA ===
    # British Columbia
    ("Apex Mountain Resort", "BC", "CA"),
    ("Baldy Mountain Resort", "BC", "CA"),
    ("Big White Ski Resort", "BC", "CA"),
    ("Manning Park Resort", "BC", "CA"),
    ("Phoenix Mountain", "BC", "CA"),
    ("Sasquatch Mountain Resort", "BC", "CA"),
    ("Shames Mountain", "BC", "CA"),
    # Alberta
    ("Castle Mountain Resort", "AB", "CA"),
    ("Pass Powderkeg", "AB", "CA"),
    # Yukon
    ("Whitehorse Nordic Ski Society", "YT", "CA"),
    # Ontario
    ("Calabogie Peaks", "ON", "CA"),
    ("Hockley Valley Resort", "ON", "CA"),
    ("Loch Lomond Ski Area", "ON", "CA"),
    ("Mont Baldy", "ON", "CA"),
    # Quebec
    ("Camp Fortune", "QC", "CA"),
    ("Centre Vorlage", "QC", "CA"),
    ("Massif du Sud", "QC", "CA"),
    ("Mont Edouard", "QC", "CA"),
    ("Mont Rigaud", "QC", "CA"),
    ("Mont Sutton", "QC", "CA"),
    ("Owl's Head", "QC", "CA"),
    ("Ski Mont Habitant", "QC", "CA"),
    ("Ski Vallee Bleue", "QC", "CA"),
    ("Val D'Irene", "QC", "CA"),
    # Newfoundland & Labrador
    ("Marble Mountain", "NL", "CA"),
    ("Smokey Mountain", "NL", "CA"),
    # === JAPAN ===
    ("Amihari Onsen Ski Resort", "Iwate", "JP"),
    ("Ani Ski Resort", "Akita", "JP"),
    ("Aomori Spring Ski Resort", "Aomori", "JP"),
    ("Canmore Ski Village", "Hokkaido", "JP"),
    ("Cupid Valley", "Niigata", "JP"),
    ("Dynaland", "Gifu", "JP"),
    ("Geto Kogen", "Iwate", "JP"),
    ("Hirugano Kogen", "Gifu", "JP"),
    ("Kamui Ski Links", "Hokkaido", "JP"),
    ("Kiroro Snow World", "Hokkaido", "JP"),
    ("Kurohime Kogen", "Nagano", "JP"),
    ("Madarao", "Nagano", "JP"),
    ("Maiko Snow Resort", "Niigata", "JP"),
    ("Nayoro Piyashiri", "Hokkaido", "JP"),
    ("Ninox Snow Park", "Niigata", "JP"),
    ("Nozawa Onsen", "Nagano", "JP"),
    ("Okunaakayama Kogen", "Gifu", "JP"),
    ("Palcall Tsumagoi", "Gunma", "JP"),
    ("Pippu Ski Resort", "Hokkaido", "JP"),
    ("Shimokura Ski Resort", "Niigata", "JP"),
    ("Takasu Snow Park", "Gifu", "JP"),
    ("Tazawako Ski Resort", "Akita", "JP"),
    ("Togakushi", "Nagano", "JP"),
    ("Washigatake", "Gifu", "JP"),
    ("WhitePIA Takasu", "Gifu", "JP"),
    ("Yubari Resort Mount Racey", "Hokkaido", "JP"),
    ("Yuzawa Nakazato", "Niigata", "JP"),
    # === EUROPE ===
    # Austria
    ("Axamer Lizum", "Tyrol", "AT"),
    ("Hochzeiger Pitztal", "Tyrol", "AT"),
    ("Kaunertaler Gletscher", "Tyrol", "AT"),
    ("Pitztaler Gletscher", "Tyrol", "AT"),
    ("Rauriser Hochalmbahnen", "Salzburg", "AT"),
    ("Steinplatte Waidring", "Tyrol", "AT"),
    ("Brixen im Thale SkiWelt", "Tyrol", "AT"),
    # Switzerland
    ("Bergbahnen Hohsaas", "Valais", "CH"),
    ("Champery", "Valais", "CH"),
    ("Leukerbad Torrent", "Valais", "CH"),
    # France
    ("Abondance", "Northern Alps", "FR"),
    ("Chatel", "Northern Alps", "FR"),
    # Italy
    ("Pila", "Aosta Valley", "IT"),
    # Germany
    ("OK Bergbahnen", "Bavaria", "DE"),
    # Spain
    ("Baqueira Beret", "Catalonia", "ES"),
    # Sweden
    ("Bjorkliden", "Lapland", "SE"),
    ("Riksgransen", "Lapland", "SE"),
    # Norway
    ("Norefjell Ski and Spa", "Buskerud", "NO"),
    # Slovenia
    ("Krvavec", "Gorenjska", "SI"),
    # Czech Republic
    ("Mala Upa", "Hradec Kralove", "CZ"),
    # Scotland (GB)
    ("Glencoe Mountain Resort", "Scotland", "GB"),
    ("Glenshee Ski Centre", "Scotland", "GB"),
    # England (GB)
    ("The Snow Centre", "England", "GB"),
    ("Trafford City Snow Centre", "England", "GB"),
    # Turkey
    ("Erciyes Ski Resort", "Kayseri", "TR"),
    ("Kartalkaya Dorukkaya", "Bolu", "TR"),
    ("Palandoken Ski Resort", "Erzurum", "TR"),
    # === SOUTH AMERICA ===
    ("Corralco Mountain Resort", "Araucania", "CL"),
    # === NORDIC (XC) RESORTS (included for completeness) ===
    ("Bear Basin Nordic Center", "ID", "US"),
    ("Bethel Village Trails", "ME", "US"),
    ("Black Jack Cross Country Ski Club", "BC", "CA"),
    ("Caledonia Nordic Ski Club", "BC", "CA"),
    ("Cascade Welcome Center XC", "NY", "US"),
    ("Catamount Outdoor Family Center", "VT", "US"),
    ("Dog Creek Lodge & Nordic Center", "MT", "US"),
    ("Enchanted Forest XC", "NM", "US"),
    ("Fairmont Hot Springs Resort", "BC", "CA"),
    ("Franconia Village XC Ski Area", "NH", "US"),
    ("Garnet Hill XC", "NY", "US"),
    ("Great Glen Trails Outdoor Center", "NH", "US"),
    ("LOGE Glacier XC", "MT", "US"),
    ("Mt. Washington XC", "BC", "CA"),
    ("Plain Valley XC", "WA", "US"),
    ("Leukerbad Gemmi Nordic Resort", "Valais", "CH"),
    # Portes du Soleil sub-resorts (CH/FR border — 12 mountains)
    # These map to Champery (CH) and Chatel/Abondance (FR) already listed above
    # plus additional villages:
    ("Avoriaz", "Northern Alps", "FR"),
    ("Les Gets", "Northern Alps", "FR"),
    ("Morzine", "Northern Alps", "FR"),
    ("Morgins", "Valais", "CH"),
    ("Les Crosets", "Valais", "CH"),
    ("Torgon", "Valais", "CH"),
    ("Saint-Jean-d'Aulps", "Northern Alps", "FR"),
    ("La Chapelle-d'Abondance", "Northern Alps", "FR"),
]


def normalize_name(name: str) -> str:
    """Normalize a resort name for comparison."""
    name = name.lower().strip()
    # Remove common suffixes only (be careful not to remove meaningful words)
    # Order matters: longer phrases first
    suffix_removals = [
        " ski resort",
        " mountain resort",
        " ski area",
        " ski and snowboard",
        " ski centre",
        " ski center",
        " snow resort",
        " alpine resort",
        " all seasons resort",
        " all season resort",
        " adventure company",
        " snow park",
        " ski park",
    ]
    for r in suffix_removals:
        if name.endswith(r):
            name = name[: -len(r)]
        elif r in name:
            name = name.replace(r, "")
    # Remove trailing " resort" only if there's something before it
    if name.endswith(" resort") and len(name) > 7:
        name = name[:-7]
    # Remove parenthetical content
    name = re.sub(r"\([^)]*\)", "", name)
    # Remove "the " prefix
    name = re.sub(r"^the\s+", "", name)
    # Normalize accented characters for comparison
    name = name.replace("é", "e").replace("è", "e").replace("ê", "e")
    name = name.replace("à", "a").replace("â", "a")
    name = name.replace("î", "i").replace("ï", "i")
    name = name.replace("ö", "o").replace("ô", "o")
    name = name.replace("ü", "u").replace("û", "u").replace("ú", "u")
    name = name.replace("ä", "a").replace("å", "a")
    name = name.replace("ç", "c")
    # Normalize punctuation and whitespace
    name = re.sub(r'[\'"`\-–—.,/]', " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Common abbreviations
    name = name.replace("mt.", "mount").replace("mt ", "mount ")
    name = name.replace("st.", "saint").replace("st ", "saint ")
    return name


def similarity(a: str, b: str) -> float:
    """Return similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def state_province_matches(indy_state: str, our_state: str, our_country: str) -> bool:
    """Check if state/province info is compatible."""
    if not indy_state or not our_state:
        return True  # Can't verify, don't penalize

    indy_s = indy_state.upper().strip()
    our_s = our_state.upper().strip()

    # Direct match
    if indy_s == our_s:
        return True

    # US state codes are 2-letter
    if our_country == "US" and len(indy_s) == 2 and len(our_s) == 2:
        return indy_s == our_s

    # Canadian province mapping
    ca_provinces = {
        "BC": "BC",
        "BRITISH COLUMBIA": "BC",
        "AB": "AB",
        "ALBERTA": "AB",
        "ON": "ON",
        "ONTARIO": "ON",
        "QC": "QC",
        "QUEBEC": "QC",
        "NL": "NL",
        "NEWFOUNDLAND": "NL",
        "LABRADOR": "NL",
        "YT": "YT",
        "YUKON": "YT",
        "NS": "NS",
        "NOVA SCOTIA": "NS",
        "NB": "NB",
    }
    if our_country == "CA":
        indy_mapped = ca_provinces.get(indy_s, indy_s)
        our_mapped = ca_provinces.get(our_s, our_s)
        return indy_mapped == our_mapped

    # Japanese prefectures - loose match (names in our DB may be in kanji)
    if our_country == "JP":
        jp_map = {
            "HOKKAIDO": ["北海道", "HOKKAIDO"],
            "NAGANO": ["長野県", "長野", "NAGANO"],
            "NIIGATA": ["新潟県", "新潟", "NIIGATA"],
            "GIFU": ["岐阜県", "岐阜", "GIFU"],
            "IWATE": ["岩手県", "岩手", "IWATE"],
            "AKITA": ["秋田県", "秋田", "AKITA"],
            "AOMORI": ["青森県", "青森", "AOMORI"],
            "GUNMA": ["群馬県", "群馬", "GUNMA"],
        }
        for key, aliases in jp_map.items():
            if indy_s == key:
                if our_s in [a.upper() for a in aliases] or our_s == key:
                    return True
        # If we can't map, don't penalize
        return True

    # European resorts - state field is often region name, hard to match
    return True


# Manual overrides for known matches that fuzzy matching can't handle well.
# Maps (indy_name, indy_state, indy_country) -> our_resort_id
# Use None as resort_id to mark "not in our DB, skip fuzzy matching"
MANUAL_OVERRIDES = {
    # Portes du Soleil sub-resorts all map to our combined entry
    (
        "Champery",
        "Valais",
        "CH",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Morgins",
        "Valais",
        "CH",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Les Crosets",
        "Valais",
        "CH",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Torgon",
        "Valais",
        "CH",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Avoriaz",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Les Gets",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Morzine",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Chatel",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Abondance",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "Saint-Jean-d'Aulps",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    (
        "La Chapelle-d'Abondance",
        "Northern Alps",
        "FR",
    ): "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery",
    # Bjorkliden has its own entry in our DB
    ("Bjorkliden", "Lapland", "SE"): "fjallby-bjorkliden",
    # Brixen im Thale is part of SkiWelt in our DB
    ("Brixen im Thale SkiWelt", "Tyrol", "AT"): "skiwelt-wilder-kaiser-brixental",
    # Bergbahnen Hohsaas
    ("Bergbahnen Hohsaas", "Valais", "CH"): "hohsaas-saas-grund",
    # Norefjell
    ("Norefjell Ski and Spa", "Buskerud", "NO"): "norefjell",
    # Snow King Mountain in Jackson, WY
    ("Snow King Mountain", "WY", "US"): "snow-king-mountain-jackson",
    # Crystal Mountain MI vs WA — Indy is MI, our DB has Crystal Mountain WA
    ("Crystal Mountain", "MI", "US"): None,  # No match; our DB only has WA version
    # WhitePIA Takasu = Washigatake/White Pia in our DB
    ("WhitePIA Takasu", "Gifu", "JP"): "washigatake-white-pia",
    # Takasu Snow Park
    ("Takasu Snow Park", "Gifu", "JP"): "takasu-snow-park",
    # Steinplatte
    (
        "Steinplatte Waidring",
        "Tyrol",
        "AT",
    ): "steinplatte-winklmoosalm-waidring-reit-im-winkl",
    # Hochzeiger
    ("Hochzeiger Pitztal", "Tyrol", "AT"): "hochzeiger-jerzens",
    # Pitztaler Gletscher
    ("Pitztaler Gletscher", "Tyrol", "AT"): "pitztal-glacier-pitztaler-gletscher",
    # Tazawako
    ("Tazawako Ski Resort", "Akita", "JP"): "akitaken-tazawako",
    # Axamer Lizum
    ("Axamer Lizum", "Tyrol", "AT"): "axamer-lizum",
    # OK Bergbahnen — not in our DB (small German area)
    ("OK Bergbahnen", "Bavaria", "DE"): None,
    # Mala Upa
    ("Mala Upa", "Hradec Kralove", "CZ"): "mala-upa",
    # Kiroro Snow World = Kiroro in our DB
    ("Kiroro Snow World", "Hokkaido", "JP"): "kiroro",
    # Madarao = Madarao/Tangram in our DB
    ("Madarao", "Nagano", "JP"): "madarao-tangram",
    # Nozawa Onsen - exact match
    ("Nozawa Onsen", "Nagano", "JP"): "nozawa-onsen",
    # Marble Mountain CA
    ("Marble Mountain", "NL", "CA"): "marble-mountain-steady-brook-humber-valley",
    # Mont Edouard
    ("Mont Edouard", "QC", "CA"): "mont-edouard-lanse-saint-jean",
    # Calabogie Peaks — in our DB
    ("Calabogie Peaks", "ON", "CA"): None,  # Not in our DB as alpine resort
    # Mont Sutton
    ("Mont Sutton", "QC", "CA"): "mont-sutton",
    # Owl's Head
    ("Owl's Head", "QC", "CA"): "owls-head",
    # Corralco
    ("Corralco Mountain Resort", "Araucania", "CL"): "corralco",
    # Baqueira/Beret
    ("Baqueira Beret", "Catalonia", "ES"): "baqueira-beret",
    # Pila IT
    ("Pila", "Aosta Valley", "IT"): "pila",
    # Krvavec
    ("Krvavec", "Gorenjska", "SI"): "krvavec",
    # Riksgransen
    ("Riksgransen", "Lapland", "SE"): "riksgransen",
    # Bolton Valley
    ("Bolton Valley Resort", "VT", "US"): "bolton-valley",
    # Jay Peak
    ("Jay Peak", "VT", "US"): "jay-peak",
    # Mt. Hood Meadows
    ("Mt. Hood Meadows", "OR", "US"): "mt-hood-meadows",
    # Washigatake = Washigatake/White Pia
    ("Washigatake", "Gifu", "JP"): "washigatake-white-pia",
    # Aomori Spring
    ("Aomori Spring Ski Resort", "Aomori", "JP"): "aomori-spring",
    # Dynaland
    ("Dynaland", "Gifu", "JP"): "dynaland",
    # Geto Kogen
    ("Geto Kogen", "Iwate", "JP"): "geto-kogen",
    # Kamui Ski Links
    ("Kamui Ski Links", "Hokkaido", "JP"): "kamui-ski-links",
    # Togakushi
    ("Togakushi", "Nagano", "JP"): "togakushi",
    # Palcall Tsumagoi
    ("Palcall Tsumagoi", "Gunma", "JP"): "palcall-tsumagoi",
    # Yubari Resort Mount Racey
    ("Yubari Resort Mount Racey", "Hokkaido", "JP"): "yubari-resort-mount-racey",
    # Maiko Snow Resort
    ("Maiko Snow Resort", "Niigata", "JP"): "maiko-snow-resort",
    # Apex Mountain Resort BC
    ("Apex Mountain Resort", "BC", "CA"): "apex-mountain-resort",
    # Baldy Mountain Resort BC
    ("Baldy Mountain Resort", "BC", "CA"): "baldy-mountain-resort",
    # Big White Ski Resort BC
    ("Big White Ski Resort", "BC", "CA"): "big-white",
    # Castle Mountain Resort AB
    ("Castle Mountain Resort", "AB", "CA"): "castle-mountain",
    # Camp Fortune QC — not in our DB
    ("Camp Fortune", "QC", "CA"): None,
    # Mountain High CA — not the same as Aspen Highlands
    ("Mountain High", "CA", "US"): None,
    # Burke Mountain VT — NOT Buttermilk Mountain
    ("Burke Mountain", "VT", "US"): None,
    # White Pass WA — NOT Stevens Pass
    ("White Pass", "WA", "US"): None,
    # Bear Valley CA — NOT Big Bear
    ("Bear Valley Mountain Resort", "CA", "US"): None,
    ("Bear Valley Adventure Company", "CA", "US"): None,
    # Magic Mountain VT — NOT Aspen Mountain
    ("Magic Mountain", "VT", "US"): None,
    # Magic Mountain ID — also not in our DB
    ("Magic Mountain", "ID", "US"): None,
    # Phoenix Mountain BC — not in our DB
    ("Phoenix Mountain", "BC", "CA"): None,
    # Shames Mountain BC — not in our DB
    ("Shames Mountain", "BC", "CA"): None,
    # Mont Rigaud QC — NOT Mont Blanc
    ("Mont Rigaud", "QC", "CA"): None,
    # Amihari Onsen — NOT Ikenotaira Onsen (different resort)
    ("Amihari Onsen Ski Resort", "Iwate", "JP"): None,
    # Okunaakayama Kogen — NOT Appi Kogen
    ("Okunaakayama Kogen", "Gifu", "JP"): None,
    # Hirugano Kogen — NOT Shigakogen/Appi
    ("Hirugano Kogen", "Gifu", "JP"): None,
    # Kurohime Kogen — NOT Appi Kogen
    ("Kurohime Kogen", "Nagano", "JP"): None,
    # Kaunertaler Gletscher — not in our DB
    ("Kaunertaler Gletscher", "Tyrol", "AT"): None,
    # Rauriser Hochalmbahnen — not in our DB
    ("Rauriser Hochalmbahnen", "Salzburg", "AT"): None,
    # Leukerbad Torrent — not in our DB
    ("Leukerbad Torrent", "Valais", "CH"): None,
    # Erciyes — not in our DB (Turkey)
    ("Erciyes Ski Resort", "Kayseri", "TR"): None,
    # Kartalkaya — not in our DB (Turkey)
    ("Kartalkaya Dorukkaya", "Bolu", "TR"): None,
    # Palandoken — not in our DB (Turkey)
    ("Palandoken Ski Resort", "Erzurum", "TR"): None,
    # Glencoe/Glenshee — not in our DB (Scotland)
    ("Glencoe Mountain Resort", "Scotland", "GB"): None,
    ("Glenshee Ski Centre", "Scotland", "GB"): None,
    # Black Mountain NH — NOT Buttermilk Mountain (false match on "mountain")
    ("Black Mountain", "NH", "US"): None,
    # All remaining US resorts with "Mountain" that keep false-matching:
    ("Tussey Mountain", "PA", "US"): None,
    ("Pine Mountain", "MI", "US"): None,
    ("Cannon Mountain", "NH", "US"): None,
    ("Ragged Mountain", "NH", "US"): None,
    ("Tenney Mountain", "NH", "US"): None,
    ("Titus Mountain", "NY", "US"): None,
    ("West Mountain", "NY", "US"): None,
    ("Shawnee Mountain", "PA", "US"): None,
    ("Silver Mountain", "ID", "US"): None,
    ("Soldier Mountain", "ID", "US"): None,
    ("Blacktail Mountain", "MT", "US"): None,
    ("Beaver Mountain", "UT", "US"): None,
    ("Echo Mountain", "CO", "US"): None,
    ("Sundown Mountain", "IA", "US"): None,
    ("Marquette Mountain", "MI", "US"): None,
    ("Lutsen Mountains", "MN", "US"): None,
    ("Spirit Mountain", "MN", "US"): None,
    ("Christie Mountain", "WI", "US"): None,
    ("Bousquet Mountain", "MA", "US"): None,
}

# Resorts to skip matching (too small/XC/indoor, or not a real match in our DB)
SKIP_MATCHING = {
    "The Snow Centre",  # Indoor UK
    "Trafford City Snow Centre",  # Indoor UK
    "Bear Basin Nordic Center",  # XC only
    "Bethel Village Trails",  # XC only
    "Black Jack Cross Country Ski Club",  # XC only
    "Caledonia Nordic Ski Club",  # XC only
    "Cascade Welcome Center XC",  # XC only
    "Catamount Outdoor Family Center",  # XC only
    "Dog Creek Lodge & Nordic Center",  # XC only
    "Enchanted Forest XC",  # XC only
    "Fairmont Hot Springs Resort",  # Hot springs, not in our DB as ski resort
    "Franconia Village XC Ski Area",  # XC only
    "Garnet Hill XC",  # XC only
    "Great Glen Trails Outdoor Center",  # XC only
    "LOGE Glacier XC",  # XC only
    "Mt. Washington XC",  # XC only (different from Mt. Washington alpine)
    "Plain Valley XC",  # XC only
    "Leukerbad Gemmi Nordic Resort",  # XC only
    "Whitehorse Nordic Ski Society",  # XC only
}


def match_resorts():
    """Match Indy Pass resorts against our database."""
    with open(RESORTS_JSON) as f:
        data = json.load(f)

    our_resorts = data["resorts"]

    # Build a lookup by resort_id for manual overrides
    resort_by_id = {r["resort_id"]: r for r in our_resorts}

    # Pre-compute normalized names for our resorts
    our_normalized = []
    for r in our_resorts:
        our_normalized.append(
            {
                "resort": r,
                "norm_name": normalize_name(r["name"]),
                "name_lower": r["name"].lower(),
            }
        )

    matches = {}
    unmatched = []
    ambiguous = []

    for indy_name, indy_state, indy_country in INDY_RESORTS:
        # Skip XC/indoor resorts
        if indy_name in SKIP_MATCHING:
            continue

        # Check manual overrides first (keyed by name, state, country)
        override_key = (indy_name, indy_state, indy_country)
        if override_key in MANUAL_OVERRIDES:
            override_id = MANUAL_OVERRIDES[override_key]
            if override_id is None:
                # Explicitly set to None means "not in our DB, skip fuzzy matching"
                unmatched.append(
                    {
                        "indy_name": indy_name,
                        "indy_state": indy_state,
                        "indy_country": indy_country,
                        "best_score": 0,
                        "best_match": None,
                        "manual_skip": True,
                    }
                )
                continue
            elif override_id in resort_by_id:
                r = resort_by_id[override_id]
                # Don't duplicate if this resort_id is already matched (e.g., Portes du Soleil)
                if override_id not in matches:
                    matches[override_id] = {
                        "indy_name": indy_name,
                        "our_name": r["name"],
                        "match_confidence": "high",
                        "match_score": 1.0,
                        "indy_state": indy_state,
                        "indy_country": indy_country,
                        "manual_match": True,
                    }
                else:
                    # Already matched, just note the alias
                    existing = matches[override_id]
                    if "indy_aliases" not in existing:
                        existing["indy_aliases"] = []
                    existing["indy_aliases"].append(indy_name)
                continue

        indy_norm = normalize_name(indy_name)
        indy_lower = indy_name.lower()

        best_match = None
        best_score = 0.0
        best_resort = None
        candidates = []

        for entry in our_normalized:
            r = entry["resort"]
            our_norm = entry["norm_name"]
            our_lower = entry["name_lower"]

            # Country must match
            country_ok = r["country"] == indy_country
            if not country_ok:
                continue

            # Check state match first for US/CA to avoid cross-state false positives
            state_ok = state_province_matches(
                indy_state, r.get("state_province", ""), r["country"]
            )

            # Compute similarity on normalized names
            score = similarity(indy_norm, our_norm)

            # Exact match on full lowercase name
            if indy_lower == our_lower:
                score = 1.0

            # Check if one normalized name is contained in the other (only if meaningful)
            if len(indy_norm) >= 4 and len(our_norm) >= 4:
                if indy_norm == our_norm:
                    score = max(score, 0.95)
                elif indy_norm in our_norm or our_norm in indy_norm:
                    # Only boost if the contained part is substantial
                    shorter = min(len(indy_norm), len(our_norm))
                    longer = max(len(indy_norm), len(our_norm))
                    if shorter / longer > 0.5:
                        score = max(score, 0.85)

            # Word overlap bonus (e.g., "bolton valley" matches "bolton valley")
            indy_words = set(indy_norm.split())
            our_words = set(our_norm.split())
            if indy_words and our_words:
                common = indy_words & our_words
                # Require meaningful word overlap, not just "ski" or "mountain"
                meaningful_common = common - {
                    "ski",
                    "mountain",
                    "mount",
                    "resort",
                    "park",
                    "snow",
                    "valley",
                    "peak",
                }
                if meaningful_common:
                    overlap = len(common) / max(len(indy_words), len(our_words))
                    if overlap >= 0.5:
                        score = max(score, 0.6 + overlap * 0.35)

            # Heavy penalty for wrong state in US/CA
            if not state_ok and r["country"] in ("US", "CA"):
                score *= 0.3

            if score > 0.55:
                candidates.append((score, r))

            if score > best_score:
                best_score = score
                best_resort = r

        # Sort candidates by score
        candidates.sort(key=lambda x: -x[0])

        # Higher threshold to avoid false positives
        if best_score >= 0.82:
            confidence = "high" if best_score >= 0.92 else "medium"

            # Check for ambiguity: multiple candidates with close scores
            if len(candidates) > 1 and candidates[1][0] > 0.78:
                confidence = "medium"
                ambiguous.append(
                    {
                        "indy_name": indy_name,
                        "indy_state": indy_state,
                        "candidates": [
                            (c[0], c[1]["resort_id"], c[1]["name"])
                            for c in candidates[:3]
                        ],
                    }
                )

            matches[best_resort["resort_id"]] = {
                "indy_name": indy_name,
                "our_name": best_resort["name"],
                "match_confidence": confidence,
                "match_score": round(best_score, 3),
                "indy_state": indy_state,
                "indy_country": indy_country,
            }
        elif best_score >= 0.70:
            # Low confidence match — flag for review
            matches[best_resort["resort_id"]] = {
                "indy_name": indy_name,
                "our_name": best_resort["name"],
                "match_confidence": "low",
                "match_score": round(best_score, 3),
                "indy_state": indy_state,
                "indy_country": indy_country,
            }
            ambiguous.append(
                {
                    "indy_name": indy_name,
                    "indy_state": indy_state,
                    "candidates": [
                        (c[0], c[1]["resort_id"], c[1]["name"]) for c in candidates[:3]
                    ],
                }
            )
        else:
            unmatched.append(
                {
                    "indy_name": indy_name,
                    "indy_state": indy_state,
                    "indy_country": indy_country,
                    "best_score": round(best_score, 3) if best_resort else 0,
                    "best_match": best_resort["name"] if best_resort else None,
                }
            )

    return matches, unmatched, ambiguous


def try_scrape_live():
    """
    Attempt to scrape the live Indy Pass resort page.
    Returns a list of resort names if successful, None otherwise.
    """
    try:
        import urllib.request

        url = "https://www.indyskipass.com/resorts/"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")

        # Try to extract resort names from the HTML
        # The page uses JS rendering, so this may not yield much
        names = re.findall(
            r'class="[^"]*resort[^"]*"[^>]*>([^<]+)<', html, re.IGNORECASE
        )
        if names:
            print(f"  Live scrape found {len(names)} resort name elements")
            return names

        # Try JSON-LD or structured data
        json_blocks = re.findall(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data, dict) and "itemListElement" in data:
                    return [
                        item.get("name")
                        for item in data["itemListElement"]
                        if item.get("name")
                    ]
            except json.JSONDecodeError:
                pass

        print(
            "  Live scrape: page loaded but resort names not found in static HTML (JS-rendered)"
        )
        return None
    except Exception as e:
        print(f"  Live scrape failed: {e}")
        return None


def main():
    print("=" * 70)
    print("Indy Pass 2025-26 Resort Matcher")
    print("=" * 70)

    # Step 1: Try live scrape (informational only — we have compiled data)
    print("\n[1] Attempting live scrape of indyskipass.com/resorts/ ...")
    live_names = try_scrape_live()
    if live_names:
        print(f"  Got {len(live_names)} names from live scrape (for cross-reference)")
    else:
        print("  Using compiled resort list from multiple sources")

    # Step 2: Match
    print(
        f"\n[2] Matching {len(INDY_RESORTS)} Indy Pass resorts against {RESORTS_JSON.name} ..."
    )
    matches, unmatched, ambiguous = match_resorts()

    # Step 3: Save output
    print(f"\n[3] Saving results to {OUTPUT_JSON.relative_to(REPO_ROOT)} ...")

    # Clean up matches for output format
    clean_matches = {}
    for resort_id, m in matches.items():
        entry = {
            "indy_name": m["indy_name"],
            "our_name": m["our_name"],
            "match_confidence": m["match_confidence"],
            "indy_pass_level": "full",  # All Indy Pass resorts offer 2 days on full pass
        }
        if "indy_aliases" in m:
            entry["indy_aliases"] = m["indy_aliases"]
        clean_matches[resort_id] = entry

    output = {
        "_metadata": {
            "season": "2025-26",
            "generated_at": "2026-02-26",
            "total_indy_resorts_in_list": len(INDY_RESORTS),
            "total_matched": len(matches),
            "total_unmatched": len(unmatched),
            "total_skipped_xc_indoor": len(SKIP_MATCHING),
            "confidence_breakdown": {
                "high": sum(
                    1 for m in matches.values() if m["match_confidence"] == "high"
                ),
                "medium": sum(
                    1 for m in matches.values() if m["match_confidence"] == "medium"
                ),
                "low": sum(
                    1 for m in matches.values() if m["match_confidence"] == "low"
                ),
            },
            "notes": [
                "Portes du Soleil (12 sub-resorts) maps to single combined entry in our DB",
                "XC-only and indoor snow centres are excluded from matching",
                "Many Indy Pass resorts are small/independent and not in our 1019-resort database",
                "Unmatched resorts are mostly small US/CA ski areas not covered by our DB",
            ],
        },
        "matches": clean_matches,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Written to {OUTPUT_JSON}")

    # Step 4: Report
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    conf = output["_metadata"]["confidence_breakdown"]
    print(f"\nTotal Indy Pass resorts in compiled list: {len(INDY_RESORTS)}")
    print(f"Matched to our database:                  {len(matches)}")
    print(f"  - High confidence:   {conf['high']}")
    print(f"  - Medium confidence: {conf['medium']}")
    print(f"  - Low confidence:    {conf['low']}")
    print(f"Unmatched (not in our DB):                {len(unmatched)}")

    if ambiguous:
        print(f"\n--- AMBIGUOUS MATCHES ({len(ambiguous)}) ---")
        for a in ambiguous:
            print(f"\n  Indy: {a['indy_name']} ({a['indy_state']})")
            for score, rid, name in a["candidates"]:
                marker = (
                    " <-- selected"
                    if score == max(c[0] for c in a["candidates"])
                    else ""
                )
                print(f"    {score:.3f}  {rid}: {name}{marker}")

    if unmatched:
        print(f"\n--- UNMATCHED RESORTS ({len(unmatched)}) ---")
        for u in sorted(unmatched, key=lambda x: x["indy_name"]):
            best = (
                f" (closest: {u['best_match']}, score={u['best_score']})"
                if u["best_match"]
                else ""
            )
            print(f"  {u['indy_name']} ({u['indy_state']}, {u['indy_country']}){best}")

    # Show matched by country
    print("\n--- MATCHES BY COUNTRY ---")
    by_country = {}
    for rid, m in matches.items():
        cc = m["indy_country"]
        by_country.setdefault(cc, []).append((rid, m))
    for cc in sorted(by_country.keys()):
        entries = by_country[cc]
        print(f"\n  {cc} ({len(entries)} matches):")
        for rid, m in sorted(entries, key=lambda x: x[1]["indy_name"]):
            conf_marker = {"high": "+", "medium": "~", "low": "?"}[
                m["match_confidence"]
            ]
            print(f"    [{conf_marker}] {m['indy_name']} -> {m['our_name']} ({rid})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
