"use client";

import React, { useEffect, useState } from "react";
import { CheckCircle2, GitBranch, X } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { TraceabilityResponse } from "@/lib/types";

export function TraceabilityModal({
  seriesCode,
  open,
  onClose,
}: {
  seriesCode: string;
  open: boolean;
  onClose: () => void;
}) {
  const [data, setData] = useState<TraceabilityResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setErr(null);
    apiFetch<TraceabilityResponse>(`/api/series/${encodeURIComponent(seriesCode)}/traceability`)
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [open, seriesCode]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-navy">
              <GitBranch className="h-4 w-4" />
              Cadena de Trazabilidad Completa
            </div>
            <h3 className="mt-1 text-lg font-semibold text-slate-900">
              {data?.series_name || seriesCode}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-slate-200 p-1 text-slate-500 hover:bg-slate-50 hover:text-slate-900"
            aria-label="Cerrar trazabilidad"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="mt-4">
          {loading && <p className="text-sm text-slate-500">Cargando linaje completo...</p>}
          {err && <p className="text-sm text-crimson">{err}</p>}
          {data && (
            <ol className="space-y-3">
              {data.steps.map((st) => (
                <li key={st.step} className="flex gap-3 rounded-lg border border-slate-100 bg-slate-50/70 p-3">
                  <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-navy text-xs font-semibold text-white">
                    {st.step}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                        {st.stage}
                      </span>
                      <CheckCircle2 className="h-3.5 w-3.5 text-teal" />
                    </div>
                    <p className="mt-0.5 break-all text-sm font-medium text-slate-900">{st.label}</p>
                    <p className="mt-0.5 break-all text-xs text-slate-600">{st.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}
