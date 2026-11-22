"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowRight, CheckCircle2, Filter } from "lucide-react";
import { apiFetch, categoryLabel, formatMonthYear, formatNumber, frequencyLabel } from "@/lib/api";
import type { CategorySummary, SeriesCard } from "@/lib/types";

function ExplorarContent() {
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get("category") || "ALL";

  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [seriesList, setSeriesList] = useState<SeriesCard[]>([]);
  const [selectedCategory, setSelectedCategory] = useState(initialCategory);
  const [selectedType, setSelectedType] = useState("ALL");
  const [filterText, setFilterText] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setSelectedCategory(searchParams.get("category") || "ALL");
  }, [searchParams]);

  useEffect(() => {
    Promise.all([
      apiFetch<CategorySummary[]>("/api/categories"),
      apiFetch<SeriesCard[]>("/api/series"),
    ])
      .then(([cats, sers]) => {
        setCategories(cats);
        setSeriesList(sers);
      })
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(() => {
    const q = filterText.trim().toLowerCase();
    return seriesList.filter((s) => {
      if (selectedCategory !== "ALL" && s.category !== selectedCategory) return false;
      if (selectedType !== "ALL" && s.series_type !== selectedType) return false;
      if (q) {
        const hay = `${s.series_name} ${s.short_name} ${s.series_code} ${s.description} ${s.subcategory}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [seriesList, selectedCategory, selectedType, filterText]);

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Explorar indicadores verificados</h1>
        <p className="mt-1 text-sm text-slate-600">
          Catálogo curado de series económicas oficiales (y derivadas documentadas) en estado VERIFIED.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setSelectedCategory("ALL")}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
              selectedCategory === "ALL" ? "bg-navy text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
            }`}
          >
            Todas ({seriesList.length})
          </button>
          {categories.map((c) => (
            <button
              key={c.code}
              type="button"
              onClick={() => setSelectedCategory(c.code)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                selectedCategory === c.code ? "bg-navy text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              {c.name} ({c.verified_series_count})
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            aria-label="Filtrar por tipo oficial o derivada"
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700"
          >
            <option value="ALL">OFFICIAL y DERIVED</option>
            <option value="OFFICIAL">Solo OFFICIAL</option>
            <option value="DERIVED">Solo DERIVED</option>
          </select>
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder="Filtrar por palabra clave..."
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:border-navy focus:outline-none"
          />
        </div>
      </div>

      {loading ? (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Cargando catálogo verificado...
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {filtered.map((s) => (
            <Link
              key={s.series_code}
              href={`/indicador/${s.series_code}`}
              className="group flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 transition hover:border-navy/50 hover:shadow-sm"
            >
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                      {categoryLabel(s.category)}
                    </span>
                    {s.is_context_variable && (
                      <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                        VARIABLE DE CONTEXTO
                      </span>
                    )}
                    <span
                      className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                        s.series_type === "OFFICIAL" ? "bg-emerald-50 text-emerald-800" : "bg-indigo-50 text-indigo-800"
                      }`}
                    >
                      {s.series_type}
                    </span>
                  </div>
                  <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    {s.audit_status}
                  </span>
                </div>

                <h2 className="mt-2.5 text-base font-semibold text-slate-900 group-hover:text-navy">
                  {s.series_name}
                </h2>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-slate-600">{s.description}</p>
              </div>

              <div className="mt-4 flex flex-wrap items-end justify-between gap-3 border-t border-slate-100 pt-3">
                <div className="space-y-0.5 text-xs text-slate-500">
                  <div>
                    <strong className="text-slate-700">Unidad:</strong> {s.unit} · {frequencyLabel(s.frequency)}
                  </div>
                  <div>
                    <strong className="text-slate-700">Cobertura:</strong> {formatMonthYear(s.start_date)} –{" "}
                    {formatMonthYear(s.last_observation_date)}
                  </div>
                </div>
                <div className="text-right">
                  {s.latest?.latest_value !== null && s.latest?.latest_value !== undefined ? (
                    <>
                      <p className="font-mono text-base font-semibold tabular-nums text-slate-900">
                        {formatNumber(s.latest.latest_value)}
                      </p>
                      <p className="text-[11px] text-slate-500">
                        Último ({formatMonthYear(s.latest.latest_date)})
                        {s.latest.yoy_pct !== null && (
                          <span className={`ml-1.5 font-medium ${s.latest.yoy_pct >= 0 ? "text-teal" : "text-crimson"}`}>
                            {s.latest.yoy_pct >= 0 ? "+" : ""}
                            {formatNumber(s.latest.yoy_pct, 1)}% i.a.
                          </span>
                        )}
                      </p>
                    </>
                  ) : (
                    <span className="text-xs text-slate-400">Datos no disponibles</span>
                  )}
                </div>
              </div>
              <div className="mt-2 flex items-center justify-end text-xs font-medium text-navy opacity-80 group-hover:opacity-100">
                Abrir indicador <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExplorarPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-500">Cargando explorador...</div>}>
      <ExplorarContent />
    </Suspense>
  );
}
