"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Search, Sparkles } from "lucide-react";
import { apiFetch, categoryLabel, formatMonthYear, frequencyLabel } from "@/lib/api";
import type { SearchResultItem } from "@/lib/types";

const EXAMPLE_QUERIES = [
  "producción textil",
  "precio de la ropa",
  "empleo textil",
  "importaciones de prendas",
  "capacidad instalada",
  "algodón",
  "salarios textiles",
  "tipo de cambio",
];

export function SearchBar({ initialQuery = "" }: { initialQuery?: string }) {
  const [query, setQuery] = useState(initialQuery);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [expandedTerms, setExpandedTerms] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setResults([]);
      setExpandedTerms([]);
      setSearched(false);
      return;
    }

    const timer = setTimeout(() => {
      setLoading(true);
      apiFetch<{ results: SearchResultItem[]; expanded_terms: string[] }>(
        `/api/search?q=${encodeURIComponent(q)}`
      )
        .then((res) => {
          setResults(res.results);
          setExpandedTerms(res.expanded_terms || []);
          setSearched(true);
        })
        .catch(() => {
          setResults([]);
          setSearched(true);
        })
        .finally(() => setLoading(false));
    }, 220);

    return () => clearTimeout(timer);
  }, [query]);

  return (
    <div className="w-full">
      <div className="relative">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="¿Qué quieres investigar sobre la industria textil?"
          aria-label="Buscador inteligente de indicadores económicos textiles"
          className="w-full rounded-xl border border-slate-300 bg-white py-4 pl-12 pr-4 text-base text-slate-900 shadow-sm transition placeholder:text-slate-400 focus:border-navy focus:outline-none focus:ring-2 focus:ring-navy/20"
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-slate-500">Consultas sugeridas:</span>
        {EXAMPLE_QUERIES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => setQuery(ex)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 transition hover:border-navy hover:text-navy"
          >
            {ex}
          </button>
        ))}
      </div>

      {loading && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
          Buscando indicadores oficiales verificados...
        </div>
      )}

      {!loading && searched && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
            <span>
              {results.length === 0
                ? "No se encontraron indicadores verificados para esa consulta."
                : `${results.length} indicador(es) verificado(s) encontrados`}
            </span>
            {expandedTerms.length > 0 && (
              <span className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-slate-600">
                <Sparkles className="h-3 w-3 text-navy" />
                Expansión semántica: {expandedTerms.slice(0, 6).join(", ")}
              </span>
            )}
          </div>

          <div className="grid gap-3">
            {results.map((r) => (
              <Link
                key={r.series_code}
                href={`/indicador/${r.series_code}`}
                className="group block rounded-xl border border-slate-200 bg-white p-4 transition hover:border-navy/50 hover:shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                        {categoryLabel(r.category)}
                      </span>
                      {r.is_context_variable && (
                        <span className="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                          VARIABLE DE CONTEXTO
                        </span>
                      )}
                      <span
                        className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                          r.series_type === "OFFICIAL"
                            ? "bg-emerald-50 text-emerald-800"
                            : "bg-indigo-50 text-indigo-800"
                        }`}
                      >
                        {r.series_type}
                      </span>
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-teal">
                        <CheckCircle2 className="h-3 w-3" />
                        {r.audit_status}
                      </span>
                    </div>
                    <h3 className="mt-1.5 text-base font-semibold text-slate-900 group-hover:text-navy">
                      {r.series_name}
                    </h3>
                    <p className="mt-1 line-clamp-2 text-sm text-slate-600">{r.description}</p>
                    <p className="mt-2 text-xs font-medium text-navy/90">
                      Por qué coincide: {r.match_reason}
                    </p>
                  </div>
                  <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-navy" />
                </div>

                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 border-t border-slate-100 pt-2.5 text-xs text-slate-500">
                  <span>
                    <strong className="text-slate-700">Fuente:</strong> {r.source_institution}
                  </span>
                  <span>
                    <strong className="text-slate-700">Unidad:</strong> {r.unit}
                  </span>
                  <span>
                    <strong className="text-slate-700">Frecuencia:</strong> {frequencyLabel(r.frequency)}
                  </span>
                  <span>
                    <strong className="text-slate-700">Cobertura:</strong> {formatMonthYear(r.start_date)} –{" "}
                    {formatMonthYear(r.last_observation_date)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
