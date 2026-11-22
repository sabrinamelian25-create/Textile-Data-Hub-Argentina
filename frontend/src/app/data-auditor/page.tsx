"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, Clock, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { apiFetch, formatDateShort } from "@/lib/api";

interface AuditorSummary {
  total_series: number;
  counts: { VERIFIED: number; WARNING: number; PENDING: number; REJECTED: number };
  average_quality_score: number | null;
  quality_score_methodology: {
    description: string;
    weights: Array<{ dimension: string; max_points: number }>;
  };
  available_connectors: string[];
  recent_runs: Array<{
    run_id: number;
    connector_name: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    records_downloaded: number;
    records_inserted: number;
    records_updated: number;
    records_rejected: number;
    error_message: string | null;
  }>;
}

interface AuditorSeriesRow {
  series_code: string;
  series_name: string;
  short_name: string;
  category: string;
  series_type: string;
  source_institution: string | null;
  frequency: string;
  last_observation_date: string | null;
  last_extracted_at: string | null;
  audit_status: string;
  quality_score: number | null;
  revisions_detected: number;
  outliers_flagged: number;
  findings: Array<{ check_category: string; check_code: string; severity: string; message: string }>;
}

export default function DataAuditorPage() {
  const [summary, setSummary] = useState<AuditorSummary | null>(null);
  const [rows, setRows] = useState<AuditorSeriesRow[]>([]);
  const [runningConnector, setRunningConnector] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const loadData = () => {
    Promise.all([
      apiFetch<AuditorSummary>("/api/auditor/summary"),
      apiFetch<AuditorSeriesRow[]>("/api/auditor/series"),
    ])
      .then(([sum, ser]) => {
        setSummary(sum);
        setRows(ser);
      })
      .catch(() => {});
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunConnector = async (connector: string) => {
    setRunningConnector(connector);
    setMsg(null);
    try {
      await apiFetch(`/api/auditor/run/${connector}`, { method: "POST" });
      setMsg(`Conector '${connector}' ejecutado y auditado correctamente.`);
      loadData();
    } catch (e: unknown) {
      setMsg(`Error ejecutando '${connector}': ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRunningConnector(null);
    }
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <div className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-navy">
            <ShieldCheck className="h-4 w-4" />
            Módulo Central de Calidad y Procedencia
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Data Auditor</h1>
          <p className="mt-1 text-sm text-slate-600">
            Control de procedencia oficial, integridad estructural, detección de revisiones y outliers. Solo las series VERIFIED se publican en la interfaz pública.
          </p>
        </div>
      </div>

      {/* KPI Summary Cards */}
      {summary && (
        <section className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500">TOTAL SERIES</p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-900">{summary.total_series}</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
            <p className="flex items-center gap-1 text-xs font-semibold text-emerald-800">
              <CheckCircle2 className="h-3.5 w-3.5" /> VERIFIED
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-emerald-900">{summary.counts.VERIFIED}</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <p className="flex items-center gap-1 text-xs font-semibold text-amber-800">
              <AlertCircle className="h-3.5 w-3.5" /> WARNING
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-amber-900">{summary.counts.WARNING}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="flex items-center gap-1 text-xs font-semibold text-slate-600">
              <Clock className="h-3.5 w-3.5" /> PENDING
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-800">{summary.counts.PENDING}</p>
          </div>
          <div className="rounded-xl border border-red-200 bg-red-50/70 p-4">
            <p className="flex items-center gap-1 text-xs font-semibold text-crimson">
              <ShieldAlert className="h-3.5 w-3.5" /> REJECTED
            </p>
            <p className="mt-1 font-mono text-2xl font-bold text-crimson">{summary.counts.REJECTED}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-medium text-slate-500">SCORE PROMEDIO</p>
            <p className="mt-1 font-mono text-2xl font-bold text-navy">
              {summary.average_quality_score ?? "—"}
              <span className="text-xs font-normal text-slate-400">/100</span>
            </p>
          </div>
        </section>
      )}

      {/* Manual Connector Trigger */}
      {summary && (
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-900">Ejecución bajo demanda de conectores oficiales</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {summary.available_connectors.map((c) => (
              <button
                key={c}
                type="button"
                disabled={runningConnector !== null}
                onClick={() => handleRunConnector(c)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-800 hover:border-navy hover:text-navy disabled:opacity-50"
              >
                <RefreshCw className={`h-3 w-3 ${runningConnector === c ? "animate-spin" : ""}`} />
                {c}
              </button>
            ))}
          </div>
          {msg && <p className="mt-2 text-xs font-medium text-navy">{msg}</p>}
        </section>
      )}

      {/* Main Series Audit Table */}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">Estado de auditoría por indicador ({rows.length})</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-4 py-3">Serie</th>
                <th className="px-4 py-3">Fuente</th>
                <th className="px-4 py-3">Último dato</th>
                <th className="px-4 py-3">Última extracción</th>
                <th className="px-4 py-3">Audit Status</th>
                <th className="px-4 py-3">Quality Score</th>
                <th className="px-4 py-3">Hallazgos / Warnings</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r) => (
                <tr key={r.series_code} className="hover:bg-slate-50/70">
                  <td className="px-4 py-3">
                    <Link href={`/indicador/${r.series_code}`} className="font-semibold text-navy hover:underline">
                      {r.short_name}
                    </Link>
                    <div className="font-mono text-[11px] text-slate-500">
                      {r.series_code} · {r.series_type}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{r.source_institution}</td>
                  <td className="px-4 py-3 font-mono text-slate-700">{formatDateShort(r.last_observation_date)}</td>
                  <td className="px-4 py-3 font-mono text-slate-500">{formatDateShort(r.last_extracted_at)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded px-2 py-0.5 text-[11px] font-semibold ${
                        r.audit_status === "VERIFIED"
                          ? "bg-emerald-50 text-emerald-800"
                          : r.audit_status === "WARNING"
                          ? "bg-amber-50 text-amber-800"
                          : r.audit_status === "REJECTED"
                          ? "bg-red-50 text-crimson"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {r.audit_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                    {r.quality_score !== null ? `${r.quality_score}/100` : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {r.findings.length === 0 ? (
                      <span className="text-slate-400">Sin observaciones</span>
                    ) : (
                      <ul className="space-y-0.5">
                        {r.findings.slice(0, 2).map((f, idx) => (
                          <li key={idx}>
                            <span className="font-semibold">[{f.severity}]</span> {f.message}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Quality Score Methodology & Recent Runs */}
      {summary && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">Metodología del Data Quality Score (0–100)</h2>
            <p className="mt-1 text-xs text-slate-600">{summary.quality_score_methodology.description}</p>
            <ul className="mt-3 space-y-2 text-xs">
              {summary.quality_score_methodology.weights.map((w) => (
                <li key={w.dimension} className="flex items-center justify-between border-b border-slate-100 pb-1.5">
                  <span className="text-slate-700">{w.dimension}</span>
                  <span className="font-mono font-semibold text-navy">{w.max_points} pts</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">Últimas ejecuciones de extracción</h2>
            <div className="mt-3 space-y-2 text-xs">
              {summary.recent_runs.map((run) => (
                <div key={run.run_id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <div>
                    <span className="font-mono font-semibold text-slate-900">#{run.run_id} {run.connector_name}</span>
                    <p className="text-[11px] text-slate-500">
                      Descargadas: {run.records_downloaded} · Insertadas: {run.records_inserted} · Revisiones: {run.records_updated} · Rechazadas: {run.records_rejected}
                    </p>
                  </div>
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                      run.status === "SUCCESS" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-crimson"
                    }`}
                  >
                    {run.status}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
