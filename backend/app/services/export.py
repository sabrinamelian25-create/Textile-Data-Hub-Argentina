from __future__ import annotations

import csv
import io
from typing import Any
import zipfile

import openpyxl
from openpyxl.styles import Font

from app.db.models import Series


def build_metadata_rows(series_list: list[Series]) -> list[dict[str, Any]]:
    rows = []
    for s in series_list:
        rows.append({
            "series_code": s.series_code,
            "series_name": s.series_name,
            "short_name": s.short_name,
            "unit": s.unit,
            "frequency": s.frequency,
            "category": s.category,
            "is_context_variable": s.is_context_variable,
            "source": s.source.institution if s.source else "",
            "source_series_code": s.source_series_code,
            "source_url": s.source_url,
            "methodology": s.methodology_summary,
            "audit_status": s.audit_status,
            "series_type": s.series_type,
            "seasonal_adjustment": s.seasonal_adjustment,
            "price_type": s.price_type,
            "start_date": s.start_date.isoformat() if s.start_date else "",
            "last_observation_date": s.last_observation_date.isoformat() if s.last_observation_date else "",
        })
    return rows


def render_csv(headers: list[str], data_rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for r in data_rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8-sig")


def render_csv_bundle_zip(headers: list[str], data_rows: list[list[Any]], metadata_rows: list[dict[str, Any]]) -> bytes:
    data_bytes = render_csv(headers, data_rows)
    meta_headers = list(metadata_rows[0].keys()) if metadata_rows else []
    meta_data = [[m.get(h, "") for h in meta_headers] for m in metadata_rows]
    meta_bytes = render_csv(meta_headers, meta_data)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("datos.csv", data_bytes)
        zf.writestr("metadatos.csv", meta_bytes)
    return zip_buf.getvalue()


def render_xlsx(headers: list[str], data_rows: list[list[Any]], metadata_rows: list[dict[str, Any]]) -> bytes:
    wb = openpyxl.Workbook()
    ws_data = wb.active
    ws_data.title = "datos"
    ws_data.append(headers)
    for cell in ws_data[1]:
        cell.font = Font(bold=True)
    for row in data_rows:
        ws_data.append(row)

    ws_meta = wb.create_sheet(title="metadatos")
    if metadata_rows:
        meta_headers = list(metadata_rows[0].keys())
        ws_meta.append(meta_headers)
        for cell in ws_meta[1]:
            cell.font = Font(bold=True)
        for m in metadata_rows:
            ws_meta.append([m.get(h, "") for h in meta_headers])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
