import XCTest
@testable import PowderChaser

/// Decoding and display helpers for GET /api/v1/rankings/weekend.
/// The JSON is real backend output for the Tahoe storm-week fixture
/// (backend/tests/fixtures/weekend_storm_2026_11_20.json).
final class WeekendRankingTests: XCTestCase {

    private let sampleJSON = """
{
  "window": {
    "start": "2026-11-20",
    "end": "2026-11-22",
    "is_default_weekend": true
  },
  "scope": "favorites",
  "passes": [],
  "rankings": [
    {
      "resort_id": "mt-rose",
      "name": "Mt. Rose Ski Tahoe",
      "region": "na_west",
      "state_province": "NV",
      "passes": [],
      "rank": 1,
      "score": 55,
      "forecast_window_cm": 9.3,
      "snowfall_7d_cm": 81.5,
      "base_depth_cm": 71.1,
      "terrain_open_pct": 53.7,
      "lifts_open": 4,
      "lifts_total": 8,
      "runs_open": 36,
      "runs_total": 67,
      "snow_score": null,
      "accessible_days": 3,
      "window_days": 3,
      "access_status": "open",
      "best_day": "2026-11-20",
      "best_day_label": "powder day",
      "components": {
        "forecast": 0.311,
        "recent": 0.87,
        "base": 0.589,
        "terrain": 0.537
      },
      "flags": [],
      "reason": "9 cm forecast Fri-Sun · 82 cm last 7 days · 71 cm base · 54% terrain open",
      "days": [
        {
          "date": "2026-11-20",
          "access": "open",
          "forecast_snow_cm": 2.5,
          "powder_cm": 31.6,
          "note": null
        },
        {
          "date": "2026-11-21",
          "access": "open",
          "forecast_snow_cm": 0,
          "powder_cm": 2.5,
          "note": null
        },
        {
          "date": "2026-11-22",
          "access": "open",
          "forecast_snow_cm": 6.8,
          "powder_cm": 3.4,
          "note": null
        }
      ]
    },
    {
      "resort_id": "sugar-bowl",
      "name": "Sugar Bowl Resort",
      "region": "na_west",
      "state_province": "CA",
      "passes": [],
      "rank": 5,
      "score": 33,
      "forecast_window_cm": 16.5,
      "snowfall_7d_cm": 87.6,
      "base_depth_cm": 83.8,
      "terrain_open_pct": null,
      "lifts_open": 0,
      "lifts_total": 12,
      "runs_open": null,
      "runs_total": null,
      "snow_score": null,
      "accessible_days": 0,
      "window_days": 3,
      "access_status": "passholder_only",
      "best_day": null,
      "best_day_label": null,
      "components": {
        "forecast": 0.483,
        "recent": 0.888,
        "base": 0.649
      },
      "flags": [
        "Passholders only 2 of 3 days (sugar-bowl)",
        "Opens Nov 21",
        "No lift/terrain data"
      ],
      "reason": "16 cm forecast Fri-Sun · 88 cm last 7 days · 84 cm base",
      "days": [
        {
          "date": "2026-11-20",
          "access": "closed",
          "forecast_snow_cm": 3.6,
          "powder_cm": 19.8,
          "note": "Opens Nov 21"
        },
        {
          "date": "2026-11-21",
          "access": "passholder_only",
          "forecast_snow_cm": 0,
          "powder_cm": 3.6,
          "note": "Sugar Bowl season passholders only; public opens Nov 27"
        },
        {
          "date": "2026-11-22",
          "access": "passholder_only",
          "forecast_snow_cm": 12.9,
          "powder_cm": 6.5,
          "note": "Sugar Bowl season passholders only; public opens Nov 27"
        }
      ]
    }
  ],
  "count": 2,
  "candidates": 8,
  "generated_at": "2026-11-21T04:30:00+00:00"
}
"""

    private func decodeSample() throws -> WeekendRankingsResponse {
        try JSONDecoder().decode(WeekendRankingsResponse.self, from: Data(sampleJSON.utf8))
    }

    func testDecodesBackendResponse() throws {
        let response = try decodeSample()
        XCTAssertEqual(response.window.start, "2026-11-20")
        XCTAssertTrue(response.window.isDefaultWeekend)
        XCTAssertEqual(response.scope, "favorites")
        XCTAssertEqual(response.rankings.count, 2)
    }

    func testDecidingNumbers() throws {
        let rose = try XCTUnwrap(decodeSample().rankings.first { $0.resortId == "mt-rose" })
        XCTAssertEqual(rose.rank, 1)
        XCTAssertEqual(rose.baseDepthCm ?? 0, 71.1, accuracy: 0.01)
        XCTAssertEqual(rose.snowfall7dCm ?? 0, 81.5, accuracy: 0.01)
        XCTAssertEqual(rose.terrainText, "4/8 lifts · 36/67 runs")
        XCTAssertFalse(rose.isInaccessible)
        XCTAssertNotNil(rose.bestDayText)
    }

    func testPassholderOnlyResort() throws {
        let sugar = try XCTUnwrap(decodeSample().rankings.first { $0.resortId == "sugar-bowl" })
        XCTAssertTrue(sugar.isPassholderOnly)
        XCTAssertTrue(sugar.isInaccessible)
        XCTAssertNil(sugar.bestDayText)
        XCTAssertEqual(sugar.days.map(\.access), [.closed, .passholderOnly, .passholderOnly])
        XCTAssertTrue(sugar.flags.contains { $0.hasPrefix("Passholders only") })
    }

    func testWindowDisplayRange() {
        let single = WeekendWindow(start: "2026-11-21", end: "2026-11-21", isDefaultWeekend: true)
        XCTAssertFalse(single.displayRange.contains("–"))
        let range = WeekendWindow(start: "2026-11-20", end: "2026-11-22", isDefaultWeekend: true)
        XCTAssertTrue(range.displayRange.contains("–"))
    }

    func testTerrainTextFallsBackToPercent() throws {
        let json = """
        {"resort_id":"x","name":"X","region":null,"state_province":null,"passes":["ikon"],
         "rank":1,"score":null,"forecast_window_cm":null,"snowfall_7d_cm":null,"base_depth_cm":null,
         "terrain_open_pct":42.4,"lifts_open":null,"lifts_total":null,"runs_open":null,"runs_total":null,
         "snow_score":null,"accessible_days":1,"window_days":1,"access_status":"open","best_day":null,
         "best_day_label":null,"components":{},"flags":[],"reason":"","days":[]}
        """
        let ranking = try JSONDecoder().decode(WeekendRanking.self, from: Data(json.utf8))
        XCTAssertEqual(ranking.terrainText, "42% open")
        XCTAssertEqual(ranking.passes, ["ikon"])
    }
}
