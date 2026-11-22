"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  GitBranch,
  HelpCircle,
  Info,
} from "lucide-react";
import {
  apiFetch,
  categoryLabel,
  formatDateShort,
  formatMonthYear,
  formatNumber,
  frequencyLabel,
} from "@/lib/api";
import type { SeriesDetail, SeriesObservationsResponse } from "@/lib/types";
import { GlossaryTooltip } from "@/components/GlossaryTooltip";
import { TimeSeriesChart } from "@/components/TimeSeriesChart";
import { TraceabilityModal } from "@/components/TraceabilityModal";

type RangePreset = "1A" | "3A" | "5A" | "10A" | "MAX" | "CUSTOM";
type TransformMode = "level" | "mom_pct" | "yoy_pct" | "base_100";

function subtractYearsIso(endIso: string, years: number): string {
  const [y, m, d] = endIso.split("-").map(Number);
  const targetY = Math.max(1990, y - years);
  return `${targetY}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function IndicadorDetailClient({ initialCode }: { initialCode?: string }) {
  const params = useParams<{ series_code: string }>();
  const seriesCode = initialCode || params?.series_code || "";

  const [detail, setDetail] = useState<SeriesDetail | null>(null);
  const [obsResp, setObsResp] = useState<SeriesObservationsResponse | null>(null);
  const [rangePreset, setRangePreset] = useState<RangePreset>("5A");
  const [customStart, setCustomStart] = useState("");
  const [customEnd, setCustomEnd] = useState("");
  const [transform, setTransform] = useState<TransformMode>("level");
  const [showMethodology, setShowMethodology] = useState(false);
  const [showTraceability, setShowTraceability] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!seriesCode) return;
    setLoading(true);
    setError(null);
    apiFetch<SeriesDetail>(`/api/series/${encodeURIComponent(seriesCode)}`)
      .then((d) => {
        setDetail(d);
        if (d.start_date) setCustomStart(d.start_date);
        if (d.end_date) setCustomEnd(d.end_date);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [seriesCode]);

  const { startDate, endDate } = useMemo(() => {
    if (!detail?.last_observation_date) return { startDate: "", endDate: "" };
    const maxD = detail.last_observation_date;
    if (rangePreset === "MAX") return { startDate: detail.start_date || "", endDate: maxD };
    if (rangePreset === "CUSTOM") return { startDate: customStart, endDate: customEnd };
    const yrs = rangePreset === "1A" ? 1 : rangePreset === "3A" ? 3 : rangePreset === "5A" ? 5 : 10;
    return { startDate: subtractYearsIso(maxD, yrs), endDate: maxD };
  }, [detail, rangePreset, customStart, customEnd]);

  useEffect(() => {
    if (!detail) return;
    const qs = new URLSearchParams({ transform });
    if (startDate) qs.set("start_date", startDate);
    if (endDate) qs.set("end_date", endDate);
    qs.set("include_revisions", "true");
    apiFetch<SeriesObservationsResponse>(
      `/api/series/${encodeURIComponent(detail.series_code)}/observations?${qs.toString()}`
    )
      .then(setObsResp)
      .catch(() => {});
  }, [detail, transform, startDate, endDate]);

  if (loading) {
    return <div className="p-8 text-sm text-slate-500">Cargando indicador oficial...</div>;
  }

  if (error || !detail) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-crimson">
        {error || "Indicador no encontrado."}
      </div>
    );
  }

  const transformUnit =
    transform === "level"
      ? detail.unit
      : transform === "base_100"
      ? `Índice Base 100 (${formatMonthYear(obsResp?.meta.base_date_used || startDate)})`
      : "Variación porcentual (%)";

  const exportQuery = new URLSearchParams({
    series: detail.series_code,
    mode: transform === "level" ? "original" : transform === "mom_pct" ? "pct_change" : transform,
  });
  if (startDate) exportQuery.set("start_date", startDate);
  if (endDate) exportQuery.set("end_date", endDate);

  return (
    <div className="space-y-8">
      <div>
        <Link href="/explorar" className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-navy">
          <ArrowLeft className="h-3.5 w-3.5" />
          Volver al explorador
        </Link>
      </div>

      {/* Header & Transparency Badges */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
            {categoryLabel(detail.category)}
          </span>
          {detail.is_context_variable && (
            <span className="rounded-md bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
              VARIABLE DE CONTEXTO (No es indicador textil)
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-semibold ${
              detail.series_type === "OFFICIAL"
                ? "bg-emerald-50 text-emerald-800"
                : "bg-indigo-50 text-indigo-800"
            }`}
          >
            Serie: {detail.series_type}
            <GlossaryTooltip termKey="official_vs_derived" />
          </span>
          <span className="inline-flex items-center gap-1 rounded-md bg-teal/10 px-2.5 py-1 text-xs font-semibold text-teal">
            <CheckCircle2 className="h-3.5 w-3.5" />
            ✓ Fuente oficial verificada · {detail.audit_status}
          </span>
          {detail.quality_score !== null && (
            <span className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600">
              Quality Score: {detail.quality_score}/100
            </span>
          )}
        </div>

        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          {detail.series_name}
        </h1>
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-slate-600">{detail.description}</p>

        {/* Nivel 1: Lectura rápida */}
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center justify-between text-xs font-medium text-slate-500">
              <span>Valor más reciente</span>
              {detail.latest?.is_preliminary && (
                <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-900">
                  PRELIMINAR <GlossaryTooltip termKey="serie_preliminar" />
                </span>
              )}
            </div>
            <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-slate-900">
              {formatNumber(detail.latest?.latest_value)}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">{detail.unit}</p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <p className="text-xs font-medium text-slate-500">Fecha del último dato</p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-900">
              {formatMonthYear(detail.latest?.latest_date)}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">Frecuencia: {frequencyLabel(detail.frequency)}</p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
              <span>Variación período anterior</span>
              <GlossaryTooltip termKey="variacion_mensual" />
            </div>
            <p
              className={`mt-1 font-mono text-2xl font-bold tabular-nums ${
                detail.latest?.mom_pct === null || detail.latest?.mom_pct === undefined
                  ? "text-slate-400"
                  : detail.latest.mom_pct >= 0
                  ? "text-teal"
                  : "text-crimson"
              }`}
            >
              {detail.latest?.mom_pct !== null && detail.latest?.mom_pct !== undefined
                ? `${detail.latest.mom_pct >= 0 ? "+" : ""}${formatNumber(detail.latest.mom_pct, 2)}%`
                : "Datos no disponibles"}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">{detail.seasonal_adjustment}</p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
            <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
              <span>Variación interanual</span>
              <GlossaryTooltip termKey="variacion_interanual" />
            </div>
            <p
              className={`mt-1 font-mono text-2xl font-bold tabular-nums ${
                detail.latest?.yoy_pct === null || detail.latest?.yoy_pct === undefined
                  ? "text-slate-400"
                  : detail.latest.yoy_pct >= 0
                  ? "text-teal"
                  : "text-crimson"
              }`}
            >
              {detail.latest?.yoy_pct !== null && detail.latest?.yoy_pct !== undefined
                ? `${detail.latest.yoy_pct >= 0 ? "+" : ""}${formatNumber(detail.latest.yoy_pct, 2)}%`
                : "Datos no disponibles"}
            </p>
            <p className="mt-0.5 text-xs text-slate-600">Mismo período año anterior</p>
          </div>
        </div>

        {/* Mandatory transparency strip */}
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1.5 border-t border-slate-100 pt-3 text-xs text-slate-600">
          <span>
            <strong>Fuente:</strong> {detail.source_institution}
          </span>
          <span>
            <strong>Última extracción:</strong> {formatDateShort(detail.last_extracted_at)}
          </span>
          <span>
            <strong>Cobertura:</strong> {formatMonthYear(detail.start_date)} – {formatMonthYear(detail.last_observation_date)} ({detail.observations_count} obs.)
          </span>
        </div>
      </section>

      {/* Main Chart + Controls */}
      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-slate-500">Período:</span>
            {(["1A", "3A", "5A", "10A", "MAX", "CUSTOM"] as RangePreset[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setRangePreset(p)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                  rangePreset === p ? "bg-navy text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {p === "MAX" ? "MÁX" : p === "CUSTOM" ? "PERSONALIZADO" : p}
              </button>
            ))}
            {rangePreset === "CUSTOM" && (
              <div className="ml-2 flex items-center gap-1.5">
                <input
                  type="date"
                  value={customStart}
                  onChange={(e) => setCustomStart(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                />
                <span className="text-xs text-slate-400">a</span>
                <input
                  type="date"
                  value={customEnd}
                  onChange={(e) => setCustomEnd(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-0.5 text-xs"
                />
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs font-medium text-slate-500">Transformación:</span>
            {[
              { key: "level", label: "NIVEL" },
              { key: "mom_pct", label: "VAR % MENSUAL" },
              { key: "yoy_pct", label: "VAR % INTERANUAL" },
              { key: "base_100", label: "BASE 100" },
            ].map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setTransform(t.key as TransformMode)}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                  transform === t.key ? "bg-teal text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                }`}
              >
                {t.label}
              </button>
            ))}
            <GlossaryTooltip termKey="indice_base_100" />
          </div>
        </div>

        {obsResp?.meta.warnings && obsResp.meta.warnings.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            {obsResp.meta.warnings.map((w, idx) => (
              <p key={idx}>{w}</p>
            ))}
          </div>
        )}

        <TimeSeriesChart
          title={`${detail.short_name} · ${transformUnit}`}
          yAxisName={transformUnit}
          series={[
            {
              name: detail.short_name,
              unit: transformUnit,
              data: obsResp?.observations || [],
            },
          ]}
        />

        <div className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs leading-relaxed text-slate-700">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-navy" />
          <div>
            <strong className="font-semibold text-slate-900">Sentido económico de la visualización: </strong>
            {detail.educational.economic_sense_note}
          </div>
        </div>
      </section>

      {/* Nivel 2: Entender este indicador */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-slate-900">Entender este indicador</h2>
        <div className="mt-5 grid gap-6 md:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-navy">¿Qué es y qué mide?</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.what_it_measures}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy">¿Cómo se construye?</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.how_it_is_built}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy">¿Cómo se interpreta?</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.interpretation_notes}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy">¿Por qué es relevante?</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.economic_relevance}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy">Limitaciones</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.limitations}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy">Resumen metodológico</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-700">{detail.educational.methodology_summary}</p>
          </div>
        </div>

        {detail.derived_lineage && (
          <div className="mt-5 rounded-lg border border-indigo-200 bg-indigo-50/60 p-4 text-xs text-indigo-950">
            <p className="font-semibold">Cálculo de serie DERIVED (v{detail.derived_lineage.calculation_version})</p>
            <p className="mt-1 font-mono">{detail.derived_lineage.formula}</p>
            <p className="mt-1 text-indigo-900">
              Series origen: {detail.derived_lineage.source_series_ids.join(", ")}
              {detail.derived_lineage.deflator_series_code && ` · Deflactor: ${detail.derived_lineage.deflator_series_code}`}
            </p>
          </div>
        )}
      </section>

      {/* Comparar con & Preguntas para investigar */}
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-teal" />
            <h2 className="text-lg font-semibold text-slate-900">Comparar con</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Variables relacionadas configuradas por categoría económica para exploración conjunta (no implica causalidad).
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {detail.suggested_comparisons.map((sc) => (
              <Link
                key={sc.series_code}
                href={`/comparar?series=${detail.series_code},${sc.series_code}&mode=base_100`}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-800 transition hover:border-teal hover:bg-emerald-50/40 hover:text-teal"
              >
                + {sc.short_name}
                {sc.is_context_variable && (
                  <span className="rounded bg-amber-100 px-1 py-0.5 text-[10px] text-amber-800">Contexto</span>
                )}
              </Link>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <HelpCircle className="h-5 w-5 text-navy" />
              <h2 className="text-lg font-semibold text-slate-900">Preguntas para investigar</h2>
            </div>
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
              PREGUNTAS EXPLORATORIAS
            </span>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            {detail.research_questions.map((rq, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1 text-xs font-bold text-navy">•</span>
                <span>{rq}</span>
              </li>
            ))}
          </ul>
          <Link
            href={`/research?primary=${detail.series_code}`}
            className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-navy hover:underline"
          >
            Llevar este indicador al Modo Research →
          </Link>
        </section>
      </div>

      {/* Descargar datos listos para research */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-lg font-semibold text-slate-900">Descargar serie</h2>
        <p className="mt-1 text-xs text-slate-600">
          Archivos listos para usar en Excel, Python, R, Stata o EViews (incluyen columna fecha, valor y archivo/hoja adicional de metadata oficial).
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          {[
            { fmt: "csv", label: "CSV (fecha, valor)" },
            { fmt: "csv_bundle", label: "CSV + Metadatos (.zip)" },
            { fmt: "xlsx", label: "Excel (.xlsx con 2 hojas)" },
            { fmt: "json", label: "JSON estructurado" },
          ].map((btn) => (
            <a
              key={btn.fmt}
              href={`/api/export?${exportQuery.toString()}&format=${btn.fmt}`}
              download
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-800 transition hover:border-navy hover:bg-slate-50 hover:text-navy"
            >
              <Download className="h-3.5 w-3.5" />
              {btn.label}
            </a>
          ))}
        </div>
      </section>

      {/* Ficha Metodológica Avanzada */}
      <section className="rounded-xl border border-slate-200 bg-white">
        <button
          type="button"
          onClick={() => setShowMethodology((v) => !v)}
          className="flex w-full items-center justify-between px-6 py-4 text-left"
        >
          <div>
            <h2 className="text-base font-semibold text-slate-900">Ficha metodológica avanzada</h2>
            <p className="text-xs text-slate-500">
              Códigos oficiales, organismo, trazabilidad raw, historial de revisiones y enlaces primarios
            </p>
          </div>
          {showMethodology ? <ChevronUp className="h-5 w-5 text-slate-500" /> : <ChevronDown className="h-5 w-5 text-slate-500" />}
        </button>

        {showMethodology && (
          <div className="border-t border-slate-200 px-6 py-5">
            <dl className="grid gap-x-6 gap-y-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
              <div><dt className="text-slate-500">series_code</dt><dd className="font-mono font-medium text-slate-900">{detail.series_code}</dd></div>
              <div><dt className="text-slate-500">source_series_code</dt><dd className="font-mono font-medium text-slate-900">{detail.source_series_code}</dd></div>
              <div><dt className="text-slate-500">Organismo</dt><dd className="font-medium text-slate-900">{detail.source_institution}</dd></div>
              <div><dt className="text-slate-500">Dataset</dt><dd className="font-medium text-slate-900">{detail.dataset.title}</dd></div>
              <div><dt className="text-slate-500">Unidad / Base</dt><dd className="font-medium text-slate-900">{detail.unit} {detail.base_period ? `(${detail.base_period})` : ""}</dd></div>
              <div><dt className="text-slate-500">Frecuencia</dt><dd className="font-medium text-slate-900">{frequencyLabel(detail.frequency)}</dd></div>
              <div><dt className="text-slate-500">Ajuste estacional</dt><dd className="font-medium text-slate-900">{detail.seasonal_adjustment}</dd></div>
              <div><dt className="text-slate-500">Tipo de precio / valor</dt><dd className="font-medium text-slate-900">{detail.price_type}</dd></div>
              <div><dt className="text-slate-500">Cobertura temporal</dt><dd className="font-medium text-slate-900">{detail.start_date} a {detail.last_observation_date}</dd></div>
              <div><dt className="text-slate-500">Última extracción</dt><dd className="font-medium text-slate-900">{detail.last_extracted_at}</dd></div>
              <div><dt className="text-slate-500">Última actualización exitosa</dt><dd className="font-medium text-slate-900">{detail.last_updated_at}</dd></div>
              <div><dt className="text-slate-500">Audit Status / Tipo</dt><dd className="font-medium text-slate-900">{detail.audit_status} · {detail.series_type}</dd></div>
            </dl>

            {detail.audit_findings.length > 0 && (
              <div className="mt-4 space-y-1.5 rounded-lg bg-slate-50 p-3 text-xs">
                <p className="font-semibold text-slate-700">Observaciones del Data Auditor:</p>
                {detail.audit_findings.map((f, i) => (
                  <p key={i} className="text-slate-600">
                    [{f.severity}] {f.message}
                  </p>
                ))}
              </div>
            )}

            <div className="mt-5 flex flex-wrap gap-3">
              <a
                href={detail.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:border-navy hover:text-navy"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                Ver fuente oficial
              </a>
              {detail.methodology_url && (
                <a
                  href={detail.methodology_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 hover:border-navy hover:text-navy"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  Metodología oficial (PDF/Web)
                </a>
              )}
              <button
                type="button"
                onClick={() => setShowTraceability(true)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3.5 py-2 text-xs font-semibold text-white hover:bg-navy/90"
              >
                <GitBranch className="h-3.5 w-3.5" />
                Ver trazabilidad
              </button>
            </div>
          </div>
        )}
      </section>

      <TraceabilityModal
        seriesCode={detail.series_code}
        open={showTraceability}
        onClose={() => setShowTraceability(false)}
      />
    </div>
  );
}
