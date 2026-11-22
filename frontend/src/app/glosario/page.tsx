"use client";

import React, { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { GlossaryItem } from "@/lib/types";

export default function GlosarioPage() {
  const [terms, setTerms] = useState<GlossaryItem[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    apiFetch<GlossaryItem[]>("/api/glossary").then(setTerms).catch(() => {});
  }, []);

  const filtered = terms.filter((t) => {
    if (!q.trim()) return true;
    const text = `${t.title} ${t.short_explanation} ${t.academic_note || ""}`.toLowerCase();
    return text.includes(q.toLowerCase());
  });

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-200 pb-4">
        <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-navy">
          <BookOpen className="h-4 w-4" />
          Referencia académica
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Glosario metodológico</h1>
        <p className="mt-1 text-sm text-slate-600">
          Conceptos estadísticos y de comercio exterior argentino explicados sin asumir conocimiento previo de nomencladores oficiales.
        </p>
      </div>

      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Filtrar término (ej: interanual, NCM, FOB, Base 100, CLAE)..."
        className="w-full max-w-md rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm focus:border-navy focus:outline-none"
      />

      <div className="grid gap-4 md:grid-cols-2">
        {filtered.map((t) => (
          <article key={t.term_key} className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-navy">{t.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{t.short_explanation}</p>
            {t.academic_note && (
              <p className="mt-3 border-t border-slate-100 pt-2.5 text-xs leading-relaxed text-slate-500">
                <strong className="text-slate-700">Nota metodológica: </strong>
                {t.academic_note}
              </p>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
