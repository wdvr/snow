#!/usr/bin/env python3
"""
Geocode the remaining resorts that failed in the first pass.
Uses manual coordinates for well-known resorts, and more aggressive search strategies for others.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp
from timezonefinder import TimezoneFinder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

RESORTS_FILE = Path(__file__).parent.parent / "data" / "resorts.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_USER_AGENT = "SnowTracker/1.0 (ski resort geocoding)"
OPEN_METEO_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

tf = TimezoneFinder()

# Manual coordinates for well-known resorts that are hard to geocode
# Format: resort_id -> (latitude, longitude)
MANUAL_COORDS = {
    # Austria
    "ehrwalder-wettersteinbahnen-ehrwald": (47.3930, 10.9210),  # Ehrwald, Tirol
    "grossglockner-resort-kals-matrei": (47.0030, 12.6440),  # Kals am Großglockner
    "pitztal-glacier-pitztaler-gletscher": (46.9190, 10.8630),  # Pitztal Glacier
    "st-jakob-im-defereggental-brunnalm": (
        46.9160,
        12.3340,
    ),  # St. Jakob, Defereggental
    "steinplatte-winklmoosalm-waidring-reit-im-winkl": (47.5920, 12.5340),  # Waidring
    "stubai-glacier-stubaier-gletscher": (47.0000, 11.1140),  # Stubaier Gletscher
    # France (some wrongly assigned to FR but are actually IT)
    "kronplatz-plan-de-corones": (46.7380, 11.9560),  # Plan de Corones, South Tyrol, IT
    "madonna-di-campiglio-pinzolo-folgarida-marilleva": (
        46.2290,
        10.8270,
    ),  # Madonna di Campiglio, IT
    "espace-villard-correncon-villard-de-lans-correncon-en-vercors": (
        45.0670,
        5.5480,
    ),  # Villard-de-Lans
    "grand-tourmalet-pic-du-midi-la-mongie-bareges": (
        42.9180,
        0.1860,
    ),  # Grand Tourmalet / La Mongie
    # Italy
    "3-zinnen-dolomites-helm-stiergarten-rotwand-kreuzbergpass": (
        46.6590,
        12.3360,
    ),  # 3 Zinnen Dolomites
    "mondole-ski-artesina-frabosa-soprana-prato-nevoso": (
        44.2630,
        7.8960,
    ),  # Mondolè Ski
    "val-senales-glacier-schnalstaler-gletscher": (
        46.7580,
        10.7760,
    ),  # Val Senales Glacier
    # Japan
    "alts-bandai": (37.5940, 140.0720),  # Alts Bandai, Fukushima
    "chuo-alps-senjojiki": (35.7670, 137.8350),  # Senjojiki, Central Alps
    "hakusan-ichirino-onsen": (36.1500, 136.5860),  # Hakusan, Ishikawa
    "jam-katsuyama": (36.0280, 136.4720),  # Katsuyama, Fukui
    "shigakogen-mountain-resort": (36.7740, 138.5250),  # Shiga Kogen, Nagano
    "winghills-shirotori-resort": (35.9090, 136.8710),  # Shirotori, Gifu
    # South Korea
    "daemyung-vivaldi-park": (37.6470, 127.6820),  # Vivaldi Park, Hongcheon
    "eagle-valley": (37.1610, 128.7150),  # Eagle Valley Resort
    "phoenix-park": (37.5830, 128.3260),  # Phoenix Park, Pyeongchang
    "star-hill-resort-cheonmasan": (37.6350, 127.3120),  # Cheonmasan, Namyangju
    # China
    "alshan-alpine": (47.1670, 119.9430),  # Alshan/Arxan, Inner Mongolia
    "changbaishan-wanda": (42.0490, 128.0570),  # Changbaishan, Jilin
    "cuiyunshan": (30.1250, 119.5770),  # Cuiyunshan, Zhejiang
    "duolemeidi-mountain-resort-chongli": (40.9580, 115.4670),  # Chongli/Zhangjiakou
    "genting-resort-secret-garden": (
        40.9750,
        115.4310,
    ),  # Chongli/Zhangjiakou (next to Duolemeidi)
    "heihe-longzhu-yuandong": (50.2440, 127.4860),  # Heihe, Heilongjiang
    "jikepulin-hemu": (48.6200, 87.0200),  # Hemu Village, Xinjiang/Altai
    "jinxiangshan": (38.8660, 116.0450),  # Jinxiangshan, near Baoding
    "jiudingshan-taiziling": (31.4550, 104.1540),  # Jiudingshan, Sichuan
    "northeast-asia-ski-center": (43.8580, 127.3090),  # Near Changchun/Jilin
    "shimao-lotus-mountain": (40.4930, 115.4730),  # Yanqing area
    "thaiwoo": (40.9420, 115.4340),  # Thaiwoo, Chongli
    "tian-qiaogou": (47.3330, 130.4180),  # Heilongjiang
    "wanlongbayi": (40.9260, 115.4020),  # Wanlong, Chongli
    "xiling-snow-mountain": (30.8970, 103.1690),  # Xiling Snow Mountain, Sichuan
    "yanqing-national-alpine-ski-centre": (40.5260, 115.7960),  # Yanqing, Beijing 2022
    # New Zealand
    "alpine-heliski": (-43.7300, 170.0960),  # Canterbury region
    "ben-ohau-heli-skiing": (-44.2500, 170.0500),  # Ben Ohau Range
    "broken-river-ski-field": (-43.1930, 171.6540),  # Canterbury
    "methven-heliski": (-43.6370, 171.6450),  # Methven area
    "queenstown-heliski": (-45.0312, 168.6626),  # Queenstown area
    "roaring-meg-resort-planned": (-45.0800, 169.0200),  # Near Cromwell (planned)
    # Argentina
    "catedral-alta-patagonia": (-41.1641, -71.4435),  # Cerro Catedral, Bariloche
    "centro-francisco-jerman": (-42.0870, -71.1540),  # Near Esquel
    "winter-park-bariloche-piedras-blancas": (-41.1500, -71.3500),  # Near Bariloche
    # Chile
    "arpa-snowcats-los-andes": (-32.8310, -70.0820),  # Los Andes
    "powder-south-heliski": (-45.4000, -71.6000),  # Aysén region
    # Germany
    "postwiesen-skidorf-neuastenberg": (51.2330, 8.5490),  # Neuastenberg
    "schwarzenlifts-eschach": (47.6880, 10.1350),  # Eschach, Allgäu
    # Spain
    "pyrenees-heliski-vielha": (42.7010, 0.7940),  # Vielha, Val d'Aran
    "san-isidro-zona-cebolledo": (43.0580, -5.3720),  # San Isidro, León
    "san-isidro-zona-salencias": (43.0580, -5.3720),  # San Isidro, León (same area)
    # Switzerland
    "elm-im-sernftal": (46.9190, 9.1750),  # Elm, Glarus
    "les-portes-du-soleil-morzine-avoriaz-les-gets-chatel-morgins-champery": (
        46.1910,
        6.7720,
    ),  # Portes du Soleil
    # Bulgaria
    "kartola-momchilovtsi": (41.6480, 24.7740),  # Momchilovtsi, Smolyan
    "ophelii": (42.2940, 24.0620),  # Near Velingrad area (estimated)
    # Czech Republic
    "herlikovice-bubakov": (50.6350, 15.5570),  # Herlíkovice, Krkonoše
    "nahoru-resort-rokytnice": (50.7280, 15.4530),  # Rokytnice nad Jizerou
    "ramzova-bonera-erak": (50.1750, 16.8530),  # Ramzová, Jeseníky
    # Finland
    "alhovuori": (61.1700, 24.3820),  # Alhovuori, near Lempäälä
    "maarianrinteet": (61.5000, 23.8130),  # Near Tampere
    "uuperi": (61.4790, 25.3130),  # Near Padasjoki
    # Poland
    "biezczadski-wa-kowa": (49.4360, 22.0790),  # Wańkowa, Bieszczady
    # Romania
    "gyergyocsomafalva-snowpark": (46.6840, 25.6840),  # Ciumani (Gyergyócsomafalva)
    # Slovenia
    "izver-sodra-ica": (45.7610, 14.4850),  # Sodražica
    "kandr-e-vidrga": (46.0240, 14.8280),  # Kandrše
    "osovje": (46.1220, 14.3290),  # Osovje, near Škofja Loka
    "park-kralja-matja-a-rna-na-koro-kem": (46.4700, 14.8500),  # Črna na Koroškem
    "smu-i-e-kotlje": (46.5220, 15.0350),  # Kotlje
    "vi-evnik-na-pokljuki": (46.3420, 13.9810),  # Viševnik, Pokljuka
    # Slovakia
    "skipark-racibor-oravsk-podzamok": (49.2600, 19.3560),  # Oravský Podzámok
    # Norway
    "tj-rhomfjellet-alsheia-skisenter-sirdal": (58.9380, 6.6630),  # Sirdal, Vest-Agder
    # Sweden
    "dundret-lapland-gallivare": (67.1110, 20.6440),  # Dundret, Gällivare
    "nasfjallet-i-salen": (61.1410, 13.2450),  # Näsfjället, Sälen
    # Australia
    "dry-slopes-urban-xtreme-brisbane": (-27.5500, 153.0540),  # Brisbane
    "winter-sports-world-western-sidney-planned": (
        -33.7930,
        150.7680,
    ),  # Western Sydney (planned)
    # US (wrongly assigned - SkiWelt is Austrian)
    "skiwelt-wilder-kaiser-brixental": (47.4430, 12.2930),  # SkiWelt, Tirol, Austria
    # Canada (wrongly assigned - Spieljoch is Austrian)
    "spieljoch-fugen": (47.1650, 11.8570),  # Spieljoch, Zillertal, Austria
}


def update_timezone(lat: float, lon: float, current_tz: str | None) -> str:
    """Get timezone from coordinates."""
    try:
        tz = tf.timezone_at(lat=lat, lng=lon)
        if tz:
            return tz
    except Exception:
        pass
    return current_tz or "UTC"


def main():
    """Apply manual coordinates to remaining zero-coord resorts."""
    logger.info(f"Loading resorts from {RESORTS_FILE}")

    with open(RESORTS_FILE, encoding="utf-8") as f:
        data = json.load(f)

    resorts = data["resorts"]
    total = len(resorts)

    zero_before = sum(
        1
        for r in resorts
        if r.get("latitude", 0) == 0.0 and r.get("longitude", 0) == 0.0
    )
    logger.info(f"Total resorts: {total}")
    logger.info(f"Currently at (0,0): {zero_before}")
    logger.info(f"Manual coordinates available: {len(MANUAL_COORDS)}")

    updated = 0
    for resort in resorts:
        if resort.get("latitude", 0) != 0.0 or resort.get("longitude", 0) != 0.0:
            continue

        resort_id = resort["resort_id"]
        if resort_id in MANUAL_COORDS:
            lat, lon = MANUAL_COORDS[resort_id]
            resort["latitude"] = lat
            resort["longitude"] = lon

            # Update timezone
            new_tz = update_timezone(lat, lon, resort.get("timezone"))
            old_tz = resort.get("timezone", "N/A")
            if new_tz != old_tz:
                resort["timezone"] = new_tz
                logger.info(
                    f"  {resort['name']}: ({lat}, {lon}) tz: {old_tz} -> {new_tz}"
                )
            else:
                logger.info(f"  {resort['name']}: ({lat}, {lon})")
            updated += 1
        else:
            logger.warning(f"  No manual coords for: {resort['name']} (id={resort_id})")

    # Write updated data
    logger.info("\nWriting updated resorts.json...")
    with open(RESORTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    zero_after = sum(
        1
        for r in resorts
        if r.get("latitude", 0) == 0.0 and r.get("longitude", 0) == 0.0
    )

    logger.info("\nRESULTS:")
    logger.info(f"  Updated: {updated}")
    logger.info(f"  Before: {zero_before} at (0,0)")
    logger.info(f"  After:  {zero_after} at (0,0)")


if __name__ == "__main__":
    main()
