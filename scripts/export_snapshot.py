from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    client = TestClient(app)

    snapshot = {
        "health": client.get("/api/health").json(),
        "categories": client.get("/api/categories").json(),
        "series_list": client.get("/api/series").json(),
        "series_detail": {},
        "series_traceability": {},
        "series_observations_raw": {},
        "trade_chain": client.get("/api/trade/chain").json(),
        "glossary": client.get("/api/glossary").json(),
        "sources": client.get("/api/sources").json(),
        "updates": client.get("/api/updates").json(),
        "auditor_summary": client.get("/api/auditor/summary").json(),
        "auditor_series": client.get("/api/auditor/series").json(),
        "industry_taxonomy": client.get("/api/industry-structure/taxonomy").json(),
        "industry_summary": client.get("/api/industry-structure/summary").json(),
        "industry_companies": [],
        "industry_presets": client.get("/api/industry-structure/research-presets").json(),
    }

    for s in snapshot["series_list"]:
        code = s["series_code"]
        snapshot["series_detail"][code] = client.get(f"/api/series/{code}").json()
        snapshot["series_traceability"][code] = client.get(f"/api/series/{code}/traceability").json()
        obs_r = client.get(f"/api/series/{code}/observations?transform=level&include_revisions=true").json()
        snapshot["series_observations_raw"][code] = {
            "observations": obs_r["observations"],
            "revisions_history": obs_r["revisions_history"],
        }

    comp_list = client.get("/api/industry-structure/companies").json()["items"]
    for c in comp_list:
        cid = c["company_id"]
        snapshot["industry_companies"].append(client.get(f"/api/industry-structure/companies/{cid}").json())

    out_dir = root / "frontend" / "public" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    snap_path = out_dir / "verified_db_snapshot.json"
    snap_path.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    src_data_dir = root / "frontend" / "src" / "data"
    src_data_dir.mkdir(parents=True, exist_ok=True)
    (src_data_dir / "series_codes.json").write_text(
        json.dumps([s["series_code"] for s in snapshot["series_list"]], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Exported snapshot: {snap_path.stat().st_size} bytes, "
        f"{len(snapshot['series_list'])} series, "
        f"{len(snapshot['industry_companies'])} companies"
    )


if __name__ == "__main__":
    main()
