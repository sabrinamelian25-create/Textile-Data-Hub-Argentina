"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { Info } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { GlossaryItem } from "@/lib/types";

const GlossaryContext = createContext<Record<string, GlossaryItem>>({});

export function GlossaryProvider({ children }: { children: React.ReactNode }) {
  const [map, setMap] = useState<Record<string, GlossaryItem>>({});

  useEffect(() => {
    apiFetch<GlossaryItem[]>("/api/glossary")
      .then((items) => {
        const next: Record<string, GlossaryItem> = {};
        for (const it of items) {
          next[it.term_key] = it;
        }
        setMap(next);
      })
      .catch(() => {
        // Non-blocking fallback
      });
  }, []);

  return <GlossaryContext.Provider value={map}>{children}</GlossaryContext.Provider>;
}

export function GlossaryTooltip({
  termKey,
  label,
  fallbackText,
}: {
  termKey: string;
  label?: string;
  fallbackText?: string;
}) {
  const glossary = useContext(GlossaryContext);
  const [open, setOpen] = useState(false);
  const item = glossary[termKey];

  const title = item?.title || label || termKey;
  const text = item?.short_explanation || fallbackText || "Definición metodológica contextual.";

  return (
    <span className="relative inline-flex items-center gap-1 align-middle">
      {label && <span>{label}</span>}
      <button
        type="button"
        aria-label={`Explicación de ${title}`}
        onClick={() => setOpen((v) => !v)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 bg-slate-100 text-slate-600 transition hover:border-navy hover:text-navy focus:outline-none focus:ring-2 focus:ring-navy/30"
      >
        <Info className="h-2.5 w-2.5" />
      </button>
      {open && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-3 text-left shadow-lg"
        >
          <p className="text-xs font-semibold text-navy">{title}</p>
          <p className="mt-1 text-xs leading-relaxed text-slate-700">{text}</p>
          {item?.academic_note && (
            <p className="mt-1.5 border-t border-slate-100 pt-1.5 text-[11px] leading-relaxed text-slate-500">
              {item.academic_note}
            </p>
          )}
        </div>
      )}
    </span>
  );
}
