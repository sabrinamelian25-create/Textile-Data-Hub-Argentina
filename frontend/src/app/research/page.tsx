"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Code2,
  Download,
  FlaskConical,
  Info,
  Sparkles,
} from "lucide-react";
import { apiFetch, categoryLabel } from "@/lib/api";
import type {
  CompareResponse,
  IndustryTaxonomy,
  ResearchSuggestion,
  SeriesCard,
  StructuralResearchFrame,
  StructuralResearchPreset,
} from "@/lib/types";
import { TimeSeriesChart } from "@/components/TimeSeriesChart";

const EXAMPLE_QUESTIONS = [
  "¿Cómo se relacionaron las importaciones con la producción textil?",
  "PyMEs vs grandes empresas en la cadena textil e indumentaria",
  "Firmas nacionales vs extranjeras y modelo productivo",
  "Producción local vs producto terminado importado",
  "Dependencia importadora por segmento de la cadena textil",
  "¿Qué pasó con el precio de la ropa frente a la inflación y los salarios?",
  "¿Cómo evolucionaron el empleo textil y la confección de prendas?",
];

function parseListParam(val: string | null): string[] {
  if (!val) return [];
  return val
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

function ResearchContent() {
  const searchParams = useSearchParams();
  const initialPrimary = searchParams.get("primary") || "";

  const [question, setQuestion] = useState("¿Cómo se relacionaron las importaciones con la producción textil?");
  const [catalog, setCatalog] = useState<SeriesCard[]>([]);
  const [suggestion, setSuggestion] = useState<ResearchSuggestion | null>(null);
  const [primaryCode, setPrimaryCode] = useState(initialPrimary || "IPI_TEXTILES");
  const [relatedCodes, setRelatedCodes] = useState<string[]>(["IMPO_CADENA_TEXTIL_TOTAL", "TC_MAYORISTA_BCRA"]);
  const [startDate, setStartDate] = useState("2017-01-01");
  const [endDate, setEndDate] = useState("");
  const [mode, setMode] = useState<"base_100" | "yoy_pct" | "original">("base_100");
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [loadingSuggest, setLoadingSuggest] = useState(false);

  // Structural dimensions integration
  const [taxonomy, setTaxonomy] = useState<IndustryTaxonomy | null>(null);
  const [presets, setPresets] = useState<StructuralResearchPreset[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [structuralFrame, setStructuralFrame] = useState<StructuralResearchFrame | null>(null);
  const [dimSizes, setDimSizes] = useState<string[]>(() => parseListParam(searchParams.get("size")));
  const [dimOrigins, setDimOrigins] = useState<string[]>(() => parseListParam(searchParams.get("origin")));
  const [dimModels, setDimModels] = useState<string[]>(() =>
    parseListParam(searchParams.get("production_model"))
  );
  const [dimChains, setDimChains] = useState<string[]>(() =>
    parseListParam(searchParams.get("chain_position"))
  );

  useEffect(() => {
    apiFetch<SeriesCard[]>("/api/series").then(setCatalog).catch(() => {});
    apiFetch<IndustryTaxonomy>("/api/industry-structure/taxonomy").then(setTaxonomy).catch(() => {});
    apiFetch<StructuralResearchPreset[]>("/api/industry-structure/research-presets")
      .then(setPresets)
      .catch(() => {});
  }, []);

  const applyFrameSeries = (frame: StructuralResearchFrame) => {
    if (frame.recommended_series.length >= 1) {
      setPrimaryCode(frame.recommended_series[0].series_code);
      setRelatedCodes(frame.recommended_series.slice(1, 4).map((s) => s.series_code));
    }
  };

  const runPresetBuilder = async (presetId: string, alsoLoadSeries = true) => {
    setActivePresetId(presetId);
    try {
      const frame = await apiFetch<StructuralResearchFrame>("/api/industry-structure/research-builder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: presetId }),
      });
      setStructuralFrame(frame);
      if (alsoLoadSeries) {
        applyFrameSeries(frame);
      }
    } catch {
      // ignore gracefully
    }
  };

  const runCustomDimensionBuilder = async () => {
    setActivePresetId(null);
    try {
      const frame = await apiFetch<StructuralResearchFrame>("/api/industry-structure/research-builder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sizes: dimSizes,
          origins: dimOrigins,
          production_models: dimModels,
          chain_positions: dimChains,
          custom_focus: question.trim() || null,
        }),
      });
      setStructuralFrame(frame);
      applyFrameSeries(frame);
    } catch {
      // ignore gracefully
    }
  };

  const handleSuggest = (qText?: string) => {
    const q = (qText ?? question).trim();
    if (!q) return;
    setLoadingSuggest(true);
    apiFetch<ResearchSuggestion>(`/api/research/suggest?q=${encodeURIComponent(q)}`)
      .then((res) => {
        setSuggestion(res);
        if (!initialPrimary && res.primary_variable?.series_code) {
          setPrimaryCode(res.primary_variable.series_code);
        }
        if (res.related_variables.length > 0) {
          setRelatedCodes(res.related_variables.slice(0, 3).map((v) => v.series_code));
        }
        if (res.structural_preset_id) {
          runPresetBuilder(res.structural_preset_id, false);
        }
      })
      .finally(() => setLoadingSuggest(false));
  };

  useEffect(() => {
    const hasIncomingDims =
      dimSizes.length > 0 || dimOrigins.length > 0 || dimModels.length > 0 || dimChains.length > 0;
    if (hasIncomingDims) {
      runCustomDimensionBuilder();
    } else {
      handleSuggest();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedAll = useMemo(() => {
    const combined = [primaryCode, ...relatedCodes.filter((c) => c !== primaryCode)].filter(Boolean);
    return combined.slice(0, 4);
  }, [primaryCode, relatedCodes]);

  useEffect(() => {
    if (selectedAll.length < 2) {
      setCompareData(null);
      return;
    }
    const qs = new URLSearchParams({
      series: selectedAll.join(","),
      mode,
      align_monthly: "avg",
    });
    if (startDate) qs.set("start_date", startDate);
    if (endDate) qs.set("end_date", endDate);
    apiFetch<CompareResponse>(`/api/compare?${qs.toString()}`)
      .then(setCompareData)
      .catch(() => setCompareData(null));
  }, [selectedAll, mode, startDate, endDate]);

  const toggleRelated = (code: string) => {
    if (code === primaryCode) return;
    setRelatedCodes((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code);
      if (prev.length >= 3) return [...prev.slice(1), code];
      return [...prev, code];
    });
  };

  const toggleDim = (setter: React.Dispatch<React.SetStateAction<string[]>>, code: string) => {
    setter((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const exportQs = new URLSearchParams({
    series: selectedAll.join(","),
    mode,
    align_monthly: "avg",
  });
  if (startDate) exportQs.set("start_date", startDate);
  if (endDate) exportQs.set("end_date", endDate);

  const pythonSnippet = `import pandas as pd\n\ndf = pd.read_csv("http://localhost:8000/api/export?${exportQs.toString()}&format=csv", parse_dates=["fecha"])\ndf.set_index("fecha", inplace=True)\nprint(df.describe())`;
  const rSnippet = `library(readr)\ndf <- read_csv("http://localhost:8000/api/export?${exportQs.toString()}&format=csv")\nsummary(df)`;

  const structureExplorerQs = new URLSearchParams();
  if (dimSizes.length) structureExplorerQs.set("size", dimSizes.join(","));
  if (dimOrigins.length) structureExplorerQs.set("origin", dimOrigins.join(","));
  if (dimModels.length) structureExplorerQs.set("production_model", dimModels.join(","));
  if (dimChains.length) structureExplorerQs.set("chain_position", dimChains.join(","));

  return (
    <div className="space-y-8">
      <div className="border-b border-slate-200 pb-4">
        <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-navy">
          <FlaskConical className="h-4 w-4" />
          Laboratorio guiado
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Empezar un research</h1>
        <p className="mt-1 text-sm text-slate-600">
          Recorrido paso a paso: formula tu pregunta, combina dimensiones de estructura empresarial con series económicas verificadas y exporta un dataset reproducible.
        </p>
      </div>

      {/* Step 1: Question */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-base font-semibold text-slate-900">1. ¿Qué quieres investigar?</h2>
        <div className="mt-3 flex flex-col gap-2 sm:flex-row">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ej: ¿Cómo se relacionaron las importaciones con la producción textil?"
            className="flex-1 rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-navy focus:outline-none"
          />
          <button
            type="button"
            onClick={() => handleSuggest()}
            disabled={loadingSuggest}
            className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-navy px-4 py-2.5 text-sm font-semibold text-white hover:bg-navy/90"
          >
            <Sparkles className="h-4 w-4" />
            Sugerir variables
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((eq) => (
            <button
              key={eq}
              type="button"
              onClick={() => {
                setQuestion(eq);
                handleSuggest(eq);
              }}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:border-navy hover:text-navy"
            >
              {eq}
            </button>
          ))}
        </div>

        {suggestion && (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs">
            <p className="font-semibold uppercase tracking-wide text-navy">{suggestion.framing_label}</p>
            <p className="mt-1 text-slate-700">{suggestion.methodological_caution}</p>
            {suggestion.exploratory_questions.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
                {suggestion.exploratory_questions.map((hq, idx) => (
                  <li key={idx}>{hq}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {/* Structural Dimensions Research Builder */}
      <section className="rounded-xl border border-indigo-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 pb-4">
          <div>
            <div className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-800">
              <Building2 className="h-3.5 w-3.5" />
              Integración con Estructura de la industria (Módulo experimental)
            </div>
            <h2 className="mt-1 text-base font-semibold text-slate-900">
              Construir preguntas usando dimensiones empresariales independientes
            </h2>
            <p className="mt-0.5 text-xs text-slate-600">
              Selecciona un eje estructural predefinido o combina Tamaño, Origen, Modelo productivo y Posición en la cadena sin mezclar categorías ni inferir causalidad.
            </p>
          </div>
          <Link
            href={`/estructura-industria${structureExplorerQs.toString() ? `?${structureExplorerQs.toString()}` : ""}`}
            className="text-xs font-semibold text-navy hover:underline"
          >
            Abrir en Estructura de la industria →
          </Link>
        </div>

        {/* 5 Structural Presets */}
        <div className="mt-4 flex flex-wrap gap-2">
          {presets.map((p) => {
            const active = activePresetId === p.preset_id;
            return (
              <button
                key={p.preset_id}
                type="button"
                onClick={() => runPresetBuilder(p.preset_id, true)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                  active
                    ? "border-navy bg-navy text-white"
                    : "border-slate-200 bg-slate-50 text-slate-800 hover:border-navy hover:text-navy"
                }`}
              >
                {p.short_label}
              </button>
            );
          })}
        </div>

        {/* Custom Combinable Dimension Selectors */}
        {taxonomy && (
          <div className="mt-4 grid gap-3 rounded-lg border border-slate-200 bg-slate-50/70 p-4 text-xs md:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="font-semibold text-slate-700">Tamaño (Dim. A)</p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                <button
                  type="button"
                  onClick={() => toggleDim(setDimSizes, "PYME")}
                  className={`rounded border px-2 py-0.5 text-[11px] ${
                    dimSizes.includes("PYME")
                      ? "border-navy bg-navy text-white"
                      : "border-indigo-200 bg-indigo-50 text-indigo-900"
                  }`}
                >
                  PyME
                </button>
                {taxonomy.dimensions
                  .find((d) => d.key === "SIZE")
                  ?.options.map((o) => (
                    <button
                      key={o.code}
                      type="button"
                      onClick={() => toggleDim(setDimSizes, o.code)}
                      className={`rounded border px-2 py-0.5 text-[11px] ${
                        dimSizes.includes(o.code)
                          ? "border-navy bg-navy text-white"
                          : "border-slate-200 bg-white text-slate-700"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
              </div>
            </div>

            <div>
              <p className="font-semibold text-slate-700">Origen (Dim. B)</p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {taxonomy.dimensions
                  .find((d) => d.key === "ORIGIN")
                  ?.options.map((o) => (
                    <button
                      key={o.code}
                      type="button"
                      onClick={() => toggleDim(setDimOrigins, o.code)}
                      className={`rounded border px-2 py-0.5 text-[11px] ${
                        dimOrigins.includes(o.code)
                          ? "border-navy bg-navy text-white"
                          : "border-slate-200 bg-white text-slate-700"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
              </div>
            </div>

            <div>
              <p className="font-semibold text-slate-700">Modelo productivo (Dim. C)</p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {taxonomy.dimensions
                  .find((d) => d.key === "PRODUCTION_MODEL")
                  ?.options.map((o) => (
                    <button
                      key={o.code}
                      type="button"
                      onClick={() => toggleDim(setDimModels, o.code)}
                      className={`rounded border px-2 py-0.5 text-[11px] ${
                        dimModels.includes(o.code)
                          ? "border-navy bg-navy text-white"
                          : "border-slate-200 bg-white text-slate-700"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
              </div>
            </div>

            <div>
              <p className="font-semibold text-slate-700">Posición cadena (Dim. D)</p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {taxonomy.dimensions
                  .find((d) => d.key === "CHAIN_POSITION")
                  ?.options.map((o) => (
                    <button
                      key={o.code}
                      type="button"
                      onClick={() => toggleDim(setDimChains, o.code)}
                      className={`rounded border px-2 py-0.5 text-[11px] ${
                        dimChains.includes(o.code)
                          ? "border-teal bg-teal text-white"
                          : "border-slate-200 bg-white text-slate-700"
                      }`}
                    >
                      {o.label}
                    </button>
                  ))}
              </div>
            </div>

            <div className="md:col-span-2 lg:col-span-4 flex justify-end pt-1">
              <button
                type="button"
                onClick={runCustomDimensionBuilder}
                className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-navy/90"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Generar marco exploratorio con esta combinación
              </button>
            </div>
          </div>
        )}

        {/* Structural Frame Result */}
        {structuralFrame && (
          <div className="mt-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-navy">{structuralFrame.title}</h3>
              <span className="font-mono text-[11px] text-slate-500">
                Dimensiones: {structuralFrame.dimensions_involved.join(" · ")}
              </span>
            </div>

            {structuralFrame.segment_comparison && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded border border-slate-200 bg-white p-3">
                  <p className="font-semibold text-slate-800">Segmento A</p>
                  <p className="mt-0.5 text-slate-600">{structuralFrame.segment_comparison.segment_a.label}</p>
                  <p className="mt-1 font-mono text-[11px] text-navy">
                    Firmas con evidencia oficial verificada:{" "}
                    <strong>{structuralFrame.segment_comparison.segment_a.verified_company_count}</strong>
                  </p>
                </div>
                <div className="rounded border border-slate-200 bg-white p-3">
                  <p className="font-semibold text-slate-800">Segmento B</p>
                  <p className="mt-0.5 text-slate-600">{structuralFrame.segment_comparison.segment_b.label}</p>
                  <p className="mt-1 font-mono text-[11px] text-navy">
                    Firmas con evidencia oficial verificada:{" "}
                    <strong>{structuralFrame.segment_comparison.segment_b.verified_company_count}</strong>
                  </p>
                </div>
              </div>
            )}

            {structuralFrame.segment_profile && (
              <div className="rounded border border-slate-200 bg-white p-3">
                <p className="font-semibold text-slate-800">Segmento seleccionado</p>
                <p className="mt-0.5 text-slate-600">{structuralFrame.segment_profile.description}</p>
                <p className="mt-1 font-mono text-[11px] text-navy">
                  Coincidencias verificadas: <strong>{structuralFrame.segment_profile.matching_companies_count}</strong>{" "}
                  de {structuralFrame.segment_profile.total_registered_companies} firmas registradas
                </p>
              </div>
            )}

            <div>
              <p className="font-semibold text-slate-800">Preguntas exploratorias sugeridas (no causales):</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-700">
                {structuralFrame.exploratory_questions.map((qItem, idx) => (
                  <li key={idx}>{qItem}</li>
                ))}
              </ul>
            </div>

            <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-[11px] text-amber-950">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
              <div>
                <p>{structuralFrame.non_causality_warning}</p>
                <p className="mt-1 text-amber-900">{structuralFrame.data_coverage_note}</p>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Steps 2, 3 & 4: Variable Selection & Range */}
      <section className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">2. Variable de interés principal</h2>
          <p className="mt-1 text-xs text-slate-500">Elige el fenómeno central que deseas explorar.</p>
          <select
            value={primaryCode}
            onChange={(e) => setPrimaryCode(e.target.value)}
            className="mt-3 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900"
          >
            {catalog.map((s) => (
              <option key={s.series_code} value={s.series_code}>
                [{categoryLabel(s.category)}] {s.short_name}
              </option>
            ))}
          </select>

          <h3 className="mt-5 text-sm font-semibold text-slate-900">4. Rango temporal y escala</h3>
          <div className="mt-2 space-y-2 text-xs">
            <label className="block text-slate-600">
              Desde:
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </label>
            <label className="block text-slate-600">
              Hasta:
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="mt-1 w-full rounded border border-slate-300 px-2.5 py-1.5"
              />
            </label>
            <label className="block text-slate-600">
              Modo de visualización:
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as "base_100" | "yoy_pct" | "original")}
                className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
              >
                <option value="base_100">Base 100 (recomendado para distintas unidades)</option>
                <option value="yoy_pct">Variación interanual (%)</option>
                <option value="original">Valores originales</option>
              </select>
            </label>
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                3. Variables relacionadas (máx. 3 adicionales)
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                Selecciona variables sectoriales o de contexto macroeconómico para contrastar hipótesis.
              </p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
              {selectedAll.length}/4 activas
            </span>
          </div>

          <div className="mt-3 grid max-h-72 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
            {catalog
              .filter((s) => s.series_code !== primaryCode)
              .map((s) => {
                const checked = relatedCodes.includes(s.series_code);
                return (
                  <button
                    key={s.series_code}
                    type="button"
                    onClick={() => toggleRelated(s.series_code)}
                    className={`flex items-start gap-2 rounded-lg border p-2.5 text-left text-xs transition ${
                      checked
                        ? "border-teal bg-emerald-50/60 text-slate-900"
                        : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <CheckCircle2
                      className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${checked ? "text-teal" : "text-slate-300"}`}
                    />
                    <div className="min-w-0">
                      <p className="font-medium leading-snug">{s.short_name}</p>
                      <p className="text-[11px] text-slate-500">
                        {s.unit} {s.is_context_variable ? "· Contexto" : ""}
                      </p>
                    </div>
                  </button>
                );
              })}
          </div>
        </div>
      </section>

      {/* Step 5: Visualization */}
      {compareData && (
        <section className="space-y-3">
          {compareData.warnings.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-950">
              <div className="flex items-center gap-1.5 font-semibold">
                <AlertTriangle className="h-4 w-4 text-amber-700" />
                Consideraciones metodológicas de tu selección
              </div>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {compareData.warnings.map((w, i) => (
                  <li key={i}>{w.message}</li>
                ))}
              </ul>
            </div>
          )}

          <TimeSeriesChart
            title={`Exploración Research · ${selectedAll.length} variables`}
            dualAxis={mode === "original" && compareData.series.length === 2}
            yAxisName={mode === "base_100" ? "Índice Base 100" : mode === "yoy_pct" ? "Var % i.a." : ""}
            series={compareData.series.map((s) => ({
              name: s.short_name,
              unit: s.unit,
              data: s.observations,
            }))}
            height={410}
          />

          <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-700">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-navy" />
            <span>{compareData.correlation_caution}</span>
          </div>
        </section>
      )}

      {/* Step 6: Export & Reproducible Code */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <h2 className="text-base font-semibold text-slate-900">6. Descargar dataset para tu trabajo de investigación</h2>
        <p className="mt-1 text-xs text-slate-600">
          Dataset limpio con fechas alineadas y hoja/archivo adicional de metadata completa para citar correctamente las fuentes oficiales.
        </p>

        <div className="mt-4 flex flex-wrap gap-3">
          {[
            { fmt: "xlsx", label: "Excel (.xlsx con hoja de metadatos)" },
            { fmt: "csv_bundle", label: "CSV + Metadatos (.zip)" },
            { fmt: "csv", label: "CSV plano" },
            { fmt: "json", label: "JSON" },
          ].map((b) => (
            <a
              key={b.fmt}
              href={`/api/export?${exportQs.toString()}&format=${b.fmt}`}
              download
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-800 hover:border-navy hover:text-navy"
            >
              <Download className="h-3.5 w-3.5" />
              {b.label}
            </a>
          ))}
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <Code2 className="h-3.5 w-3.5" /> Python (pandas)
            </div>
            <pre className="mt-2 overflow-x-auto font-mono text-[11px] text-slate-800">{pythonSnippet}</pre>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              <Code2 className="h-3.5 w-3.5" /> R (readr)
            </div>
            <pre className="mt-2 overflow-x-auto font-mono text-[11px] text-slate-800">{rSnippet}</pre>
          </div>
        </div>
      </section>
    </div>
  );
}

export default function ResearchPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">Cargando Modo Research...</div>}>
      <ResearchContent />
    </Suspense>
  );
}
