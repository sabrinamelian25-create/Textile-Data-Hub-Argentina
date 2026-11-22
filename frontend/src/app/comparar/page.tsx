"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AlertTriangle, Download, Info, Plus, X } from "lucide-react";
import { apiFetch, categoryLabel } from "@/lib/api";
import type { CompareResponse, SeriesCard } from "@/lib/types";
import { GlossaryTooltip } from "@/components/GlossaryTooltip";
import { TimeSeriesChart } from "@/components/TimeSeriesChart";

type CompareMode = "original" | "pct_change" | "yoy_pct" | "base_100";

function CompararContent() {
  const searchParams = useSearchParams();
  const initialParam = searchParams.get("series");
  const initialMode = (searchParams.get("mode") as CompareMode) || "base_100";

  const [catalog, setCatalog] = useState<SeriesCard[]>([]);
  const [selectedCodes, setSelectedCodes] = useState<string[]>(
    initialParam ? initialParam.split(",").filter(Boolean).slice(0, 4) : ["IPI_TEXTILES", "IPI_NIVEL_GENERAL_ORIG"]
  );
  const [mode, setMode] = useState<CompareMode>(initialMode);
  const [alignMonthly, setAlignMonthly] = useState<"avg" | "eop">("avg");
  const [startDate, setStartDate] = useState("2017-01-01");
  const [endDate, setEndDate] = useState("");
  const [addPick, setAddPick] = useState("");
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<SeriesCard[]>("/api/series").then(setCatalog).catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedCodes.length < 2) {
      setCompareData(null);
      return;
    }
    setLoading(true);
    setError(null);
    const qs = new URLSearchParams({
      series: selectedCodes.join(","),
      mode,
      align_monthly: alignMonthly,
    });
    if (startDate) qs.set("start_date", startDate);
    if (endDate) qs.set("end_date", endDate);

    apiFetch<CompareResponse>(`/api/compare?${qs.toString()}`)
      .then(setCompareData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedCodes, mode, alignMonthly, startDate, endDate]);

  const availableToAdd = useMemo(
    () => catalog.filter((s) => !selectedCodes.includes(s.series_code)),
    [catalog, selectedCodes]
  );

  const handleAdd = () => {
    if (!addPick || selectedCodes.includes(addPick) || selectedCodes.length >= 4) return;
    setSelectedCodes((prev) => [...prev, addPick]);
    setAddPick("");
  };

  const handleRemove = (code: string) => {
    if (selectedCodes.length <= 2) return;
    setSelectedCodes((prev) => prev.filter((c) => c !== code));
  };

  const exportQs = new URLSearchParams({
    series: selectedCodes.join(","),
    mode,
    align_monthly: alignMonthly,
  });
  if (startDate) exportQs.set("start_date", startDate);
  if (endDate) exportQs.set("end_date", endDate);

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Comparador de series (2 a 4 variables)</h1>
        <p className="mt-1 text-sm text-slate-600">
          Compara trayectorias económicas en valores originales, variación porcentual, variación interanual o Base 100.
        </p>
      </div>

      {/* Controls panel */}
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-slate-600">Series seleccionadas ({selectedCodes.length}/4):</span>
          {selectedCodes.map((code) => {
            const info = catalog.find((c) => c.series_code === code);
            return (
              <span
                key={code}
                className="inline-flex items-center gap-1.5 rounded-lg border border-navy/25 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-900"
              >
                <span>{info?.short_name || code}</span>
                {info?.is_context_variable && (
                  <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-800">Contexto</span>
                )}
                {selectedCodes.length > 2 && (
                  <button
                    type="button"
                    onClick={() => handleRemove(code)}
                    aria-label={`Quitar ${code}`}
                    className="text-slate-400 hover:text-crimson"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </span>
            );
          })}
        </div>

        {selectedCodes.length < 4 && (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={addPick}
              onChange={(e) => setAddPick(e.target.value)}
              aria-label="Seleccionar serie para agregar"
              className="max-w-md flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-800"
            >
              <option value="">+ Agregar indicador a la comparación...</option>
              {availableToAdd.map((s) => (
                <option key={s.series_code} value={s.series_code}>
                  [{categoryLabel(s.category)}] {s.short_name} ({s.unit})
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleAdd}
              disabled={!addPick}
              className="inline-flex items-center gap-1 rounded-lg bg-navy px-3.5 py-2 text-xs font-semibold text-white disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" /> Agregar
            </button>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-slate-100 pt-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-slate-500">Modo:</span>
            {[
              { k: "original", label: "VALORES ORIGINALES" },
              { k: "pct_change", label: "VARIACIÓN %" },
              { k: "yoy_pct", label: "VARIACIÓN INTERANUAL" },
              { k: "base_100", label: "BASE 100" },
            ].map((m) => (
              <button
                key={m.k}
                type="button"
                onClick={() => setMode(m.k as CompareMode)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                  mode === m.k ? "bg-teal text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {m.label}
              </button>
            ))}
            <GlossaryTooltip termKey="indice_base_100" />
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5 text-slate-600">
              Desde:
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <label className="flex items-center gap-1.5 text-slate-600">
              Hasta:
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
            </label>
            <label className="flex items-center gap-1.5 text-slate-600">
              Series diarias:
              <select
                value={alignMonthly}
                onChange={(e) => setAlignMonthly(e.target.value as "avg" | "eop")}
                className="rounded border border-slate-300 bg-white px-2 py-1 text-xs"
              >
                <option value="avg">Promedio mensual</option>
                <option value="eop">Fin de mes</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      {/* Warnings & Correlation vs Causality */}
      {compareData?.warnings && compareData.warnings.length > 0 && (
        <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-950">
          <div className="flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="h-4 w-4 text-amber-700" />
            Alertas metodológicas de comparación
          </div>
          <ul className="space-y-1 pl-5 list-disc">
            {compareData.warnings.map((w, i) => (
              <li key={i}>{w.message}</li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-crimson">{error}</div>
      )}

      {loading && <div className="p-6 text-sm text-slate-500">Calculando comparación...</div>}

      {compareData && !loading && (
        <>
          <TimeSeriesChart
            title={
              mode === "base_100"
                ? `Comparación normalizada Base 100 (referencia: ${compareData.base_date || startDate})`
                : `Comparación (${mode})`
            }
            dualAxis={mode === "original" && compareData.series.length === 2}
            yAxisName={
              mode === "base_100"
                ? "Índice Base 100"
                : mode === "original"
                ? ""
                : "Variación %"
            }
            series={compareData.series.map((s) => ({
              name: s.short_name,
              unit: s.unit,
              data: s.observations,
            }))}
            height={420}
          />

          <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-700">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-navy" />
            <div>
              <strong>Correlación ≠ Causalidad: </strong>
              {compareData.correlation_caution}{" "}
              <GlossaryTooltip termKey="correlacion_vs_causalidad" />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4">
            <div className="text-xs text-slate-600">
              <strong>Descargar dataset comparado:</strong> tabla ancha alineada por fecha lista para econometría o gráficos.
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { fmt: "csv", label: "CSV" },
                { fmt: "csv_bundle", label: "CSV + Metadatos (.zip)" },
                { fmt: "xlsx", label: "Excel (.xlsx)" },
                { fmt: "json", label: "JSON" },
              ].map((b) => (
                <a
                  key={b.fmt}
                  href={`/api/export?${exportQs.toString()}&format=${b.fmt}`}
                  download
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 hover:border-navy hover:text-navy"
                >
                  <Download className="h-3.5 w-3.5" />
                  {b.label}
                </a>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function CompararPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">Cargando comparador...</div>}>
      <CompararContent />
    </Suspense>
  );
}
