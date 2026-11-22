# Season Date Sources — 2026-27

Data verified **2026-11-21** for the 2.1.3 build. Per-resort source strings are also stored
in the `season_dates_source` field of each resort object in `resorts.json`.

## Sources used

| Abbrev | Full URL/Name |
|--------|--------------|
| OnTheSnow | https://www.onthesnow.com (named aggregator, region/projected-openings pages) |
| Unofficial Networks | https://unofficialnetworks.com |
| Teton Gravity | https://www.tetongravity.com/2026-27-ski-resort-opening-dates/ |
| tahoetruckeevacations.com | https://www.tahoetruckeevacations.com/blog/lake-tahoe-ski-resort-opening-dates |
| snocal.com | https://snocal.com/pages/california-ski-resort-opening-dates |
| South Tahoe Now | https://southtahoenow.com |
| Active NorCal | https://www.activenorcal.com |
| Tahoe Daily Tribune | https://www.tahoedailytribune.com |
| kcra.com | https://www.kcra.com/article/tahoe-ski-resort-opening-dates-2026-2027-season/ |
| sierraattahoe.com | Official resort site |
| blackcombpeaks.com | https://www.blackcombpeaks.com (Whistler local guide) |
| canadiantravelnews.ca | https://canadiantravelnews.ca |
| calgarycitizen.com | https://calgarycitizen.com (Lake Louise/SkiBig3 dates) |
| rmoutlook.com | https://www.rmoutlook.com (AB/BC ski dates) |
| mktgspace.com | https://mktgspace.com (Banff Sunshine opening) |
| bigskyresort.com | Official resort site |
| staymontana.com | https://www.staymontana.com |
| skivermont.com | https://skivermont.com/opening-dates |
| lakeshorevermont.com | https://lakeshorevermont.com |
| deeparrival.com | https://deeparrival.com (resort news) |
| pick-a-ski.com | https://www.pick-a-ski.com/en/articles/ |
| travelerstoday.com | https://www.travelerstoday.com |
| skierstash.com | https://skierstash.com/utah/ |
| skiutah.com | https://www.skiutah.com |
| afar.com | https://www.afar.com (early CO openings) |
| travelandtourworld.com | https://www.travelandtourworld.com |
| basemountainsports.com | https://www.basemountainsports.com |
| gilsonpropertygroup.com | https://gilsonpropertygroup.com (Breckenridge) |
| lodgingcompany.com | https://www.lodgingcompany.com |

## Resorts NOT in current dataset

The brief noted **Soda Springs** and **Donner Ski Ranch** as undated as of 2026-11-16.
Neither resort is in the current 1019-resort dataset; they were rechecked on 2026-11-21:
- Soda Springs: OnTheSnow shows a Nov 27 projected opening — but this is a projection.
  Since neither resort is in the current dataset, no action needed.
- Donner Ski Ranch: OnTheSnow shows a Dec 11 projected opening — same as above.

If either resort is added to the dataset in a future release, confirmed opening dates
should be sourced from the resort's own snow report page before adding.

## Coverage

| Status | Count |
|--------|-------|
| `open` | 18 |
| `pre_season` (with date) | 31 |
| `pre_season` (no date yet) | 3 (Park City delayed; Sugarloaf/Sunday River warm weather) |
| No data (not yet posted) | 967 |

Resorts with no data are predominantly: European Alps, Scandinavia, Japan, Oceania,
South America, and many NA east/interior resorts that have not posted 2026-27 dates.
