"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowRight, Info } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface TradeChainResponse {
  methodological_note: string;
  stages: Array<{
    stage_key: string;
    stage_label: string;
    ncm_chapters: Array<{
      nomenclature: string;
      product_code: string;
      official_description: string;
      analytical_group: string;
      notes: string | null;
    }>;
    linked_series: Array<{
      series_code: string;
      short_name: string;
      unit: string;
      series_type: string;
      last_observation_date: string | null;
    }>;
  }>;
}

export default function CadenaTextilPage() {
  const [data, setData] = useState<TradeChainResponse>({
    methodological_note:
      "Las series NCM a 2 dígitos provienen de SSPM / INDEC (millones de USD CIF para importaciones y FOB para exportaciones).",
    stages: [],
  });

  useEffect(() => {
    apiFetch<TradeChainResponse>("/api/trade/chain")
      .then((res) => {
        if (res?.stages) setData(res);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-8">
      <div className="border-b border-slate-200 pb-4">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          Cadena Productiva Textil y Nomenclatura NCM (Capítulos 50–63)
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          Organización analítica del comercio exterior textil argentino (Sección XI del Nomenclador Común del Mercosur) preservando los códigos oficiales.
        </p>
      </div>

      <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-950">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
        <p>{data.methodological_note}</p>
      </div>

      <div className="space-y-4">
        {data.stages.map((st, idx) => (
          <div key={st.stage_key}>
            <div className="rounded-xl border border-slate-200 bg-white p-6">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                <h2 className="text-lg font-semibold text-navy">{st.stage_label}</h2>
                <div className="flex flex-wrap gap-2">
                  {st.linked_series.map((ls) => (
                    <Link
                      key={ls.series_code}
                      href={`/indicador/${ls.series_code}`}
                      className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-800 hover:border-navy hover:text-navy"
                    >
                      {ls.short_name}
                      <ArrowRight className="h-3 w-3" />
                    </Link>
                  ))}
                </div>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {st.ncm_chapters.map((ch) => (
                  <div key={ch.product_code} className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded bg-navy px-2 py-0.5 font-mono text-xs font-semibold text-white">
                        {ch.nomenclature} Cap. {ch.product_code}
                      </span>
                      <span className="text-[11px] font-medium text-slate-500">{ch.analytical_group}</span>
                    </div>
                    <p className="mt-2 text-sm font-medium text-slate-900">{ch.official_description}</p>
                    {ch.notes && <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{ch.notes}</p>}
                  </div>
                ))}
              </div>
            </div>
            {idx < data.stages.length - 1 && (
              <div className="flex justify-center py-2">
                <ArrowDown className="h-5 w-5 text-slate-400" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
