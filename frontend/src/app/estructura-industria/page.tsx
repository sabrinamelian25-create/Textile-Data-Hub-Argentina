"use client";

import React, { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Download,
  ExternalLink,
  Filter,
  FlaskConical,
  History,
  Info,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { apiFetch, formatDateShort } from "@/lib/api";
import type {
  CompaniesListResponse,
  CompanyDetail,
  CompanyItem,
  IndustryStructureSummary,
  IndustryTaxonomy,
} from "@/lib/types";

const COMBINED_EXAMPLES = [
  {
    label: "PyME + Nacional + Producción principalmente local + Confección",
    size: ["PYME"],
    origin: ["NATIONAL"],
    production_model: ["LOCAL_PRIMARY"],
    chain_position: ["APPAREL"],
  },
  {
    label: "PyME + Nacional + Producción local con insumos importados + Tejido",
    size: ["PYME"],
    origin: ["NATIONAL"],
    production_model: ["LOCAL_IMPORTED_INPUTS"],
    chain_position: ["FABRIC"],
  },
  {
    label: "Grande + Integrada",
    size: ["LARGE"],
    origin: [],
    production_model: [],
    chain_position: ["INTEGRATED"],
  },
  {
    label: "Extranjera + Importación de producto terminado + Retail",
    size: [],
    origin: ["FOREIGN"],
    production_model: ["IMPORTED_FINISHED"],
    chain_position: ["RETAIL"],
  },
  {
    label: "Sin determinar (UNKNOWN en tamaño)",
    size: ["UNKNOWN"],
    origin: [],
    production_model: [],
    chain_position: [],
  },
];

function badgeClassForCode(code: string): string {
  if (code === "UNKNOWN") return "border-slate-200 bg-slate-100 text-slate-600";
  if (code === "VERIFIED_COMPLETE" || code === "VERIFIED")
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (code === "PARTIALLY_VERIFIED" || code === "WARNING")
    return "border-amber-200 bg-amber-50 text-amber-900";
  if (code === "REJECTED") return "border-red-200 bg-red-50 text-crimson";
  return "border-slate-200 bg-slate-50 text-slate-800";
}

function parseListParam(val: string | null): string[] {
  if (!val) return [];
  return val
    .split(",")
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);
}

function IndustryStructureContent() {
  const searchParams = useSearchParams();

  const [taxonomy, setTaxonomy] = useState<IndustryTaxonomy | null>(null);
  const [summary, setSummary] = useState<IndustryStructureSummary | null>(null);
  const [companiesResp, setCompaniesResp] = useState<CompaniesListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Combinable independent dimension filters
  const [selectedSizes, setSelectedSizes] = useState<string[]>(() => parseListParam(searchParams.get("size")));
  const [selectedOrigins, setSelectedOrigins] = useState<string[]>(() => parseListParam(searchParams.get("origin")));
  const [selectedModels, setSelectedModels] = useState<string[]>(() =>
    parseListParam(searchParams.get("production_model"))
  );
  const [selectedChains, setSelectedChains] = useState<string[]>(() =>
    parseListParam(searchParams.get("chain_position"))
  );
  const [chainMatch, setChainMatch] = useState<"any" | "all">("any");
  const [searchText, setSearchText] = useState<string>(() => searchParams.get("q") || "");

  // Modals
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [detailCompany, setDetailCompany] = useState<CompanyDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Register company form state
  const [regLegalName, setRegLegalName] = useState("");
  const [regBrandName, setRegBrandName] = useState("");
  const [regCuit, setRegCuit] = useState("");
  const [regNotes, setRegNotes] = useState("");
  const [regSubmitting, setRegSubmitting] = useState(false);
  const [regMessage, setRegMessage] = useState<string | null>(null);

  // Add classification evidence form state
  const [clsDimension, setClsDimension] = useState<"SIZE" | "ORIGIN" | "PRODUCTION_MODEL" | "CHAIN_POSITION">("SIZE");
  const [clsValue, setClsValue] = useState("UNKNOWN");
  const [clsValidFrom, setClsValidFrom] = useState(() => new Date().toISOString().slice(0, 10));
  const [clsValidTo, setClsValidTo] = useState("");
  const [clsSourceId, setClsSourceId] = useState<string>("");
  const [clsSourceUrl, setClsSourceUrl] = useState("");
  const [clsEvidence, setClsEvidence] = useState("");
  const [clsSubmitting, setClsSubmitting] = useState(false);
  const [clsAuditFeedback, setClsAuditFeedback] = useState<{
    audit_status: string;
    audit_notes: string;
    promoted_to_company: boolean;
  } | null>(null);

  const loadReferenceData = useCallback(async () => {
    try {
      const [tax, sum] = await Promise.all([
        apiFetch<IndustryTaxonomy>("/api/industry-structure/taxonomy"),
        apiFetch<IndustryStructureSummary>("/api/industry-structure/summary"),
      ]);
      setTaxonomy(tax);
      setSummary(sum);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "No se pudo cargar la taxonomía del módulo.");
    }
  }, []);

  const buildFilterQueryString = useCallback(() => {
    const qs = new URLSearchParams();
    if (selectedSizes.length > 0) qs.set("size", selectedSizes.join(","));
    if (selectedOrigins.length > 0) qs.set("origin", selectedOrigins.join(","));
    if (selectedModels.length > 0) qs.set("production_model", selectedModels.join(","));
    if (selectedChains.length > 0) qs.set("chain_position", selectedChains.join(","));
    if (selectedChains.length > 1) qs.set("chain_match", chainMatch);
    if (searchText.trim()) qs.set("q", searchText.trim());
    return qs.toString();
  }, [selectedSizes, selectedOrigins, selectedModels, selectedChains, chainMatch, searchText]);

  const loadCompanies = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = buildFilterQueryString();
      const resp = await apiFetch<CompaniesListResponse>(
        `/api/industry-structure/companies${qs ? `?${qs}` : ""}`
      );
      setCompaniesResp(resp);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error cargando empresas.");
    } finally {
      setLoading(false);
    }
  }, [buildFilterQueryString]);

  useEffect(() => {
    loadReferenceData();
  }, [loadReferenceData]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  const toggleItem = (
    setter: React.Dispatch<React.SetStateAction<string[]>>,
    code: string
  ) => {
    setter((prev) => (prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]));
  };

  const clearFilters = () => {
    setSelectedSizes([]);
    setSelectedOrigins([]);
    setSelectedModels([]);
    setSelectedChains([]);
    setChainMatch("any");
    setSearchText("");
  };

  const applyPresetExample = (ex: (typeof COMBINED_EXAMPLES)[number]) => {
    setSelectedSizes(ex.size);
    setSelectedOrigins(ex.origin);
    setSelectedModels(ex.production_model);
    setSelectedChains(ex.chain_position);
  };

  const openCompanyDetail = async (companyId: number) => {
    setLoadingDetail(true);
    setClsAuditFeedback(null);
    try {
      const det = await apiFetch<CompanyDetail>(`/api/industry-structure/companies/${companyId}`);
      setDetailCompany(det);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar el detalle de la empresa.");
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRegisterCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regLegalName.trim()) return;
    setRegSubmitting(true);
    setRegMessage(null);
    try {
      const created = await apiFetch<CompanyDetail>("/api/industry-structure/companies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          legal_name: regLegalName.trim(),
          brand_name: regBrandName.trim() || null,
          cuit: regCuit.trim() || null,
          notes: regNotes.trim() || null,
        }),
      });
      setRegLegalName("");
      setRegBrandName("");
      setRegCuit("");
      setRegNotes("");
      setShowRegisterModal(false);
      await Promise.all([loadCompanies(), loadReferenceData()]);
      setDetailCompany(created);
    } catch (err: unknown) {
      setRegMessage(err instanceof Error ? err.message : "Error registrando la empresa.");
    } finally {
      setRegSubmitting(false);
    }
  };

  const currentDimOptions = useMemo(() => {
    const dim = taxonomy?.dimensions.find((d) => d.key === clsDimension);
    return dim?.options ?? [];
  }, [taxonomy, clsDimension]);

  useEffect(() => {
    setClsValue("UNKNOWN");
  }, [clsDimension]);

  const handleSubmitClassification = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!detailCompany) return;
    setClsSubmitting(true);
    setClsAuditFeedback(null);
    try {
      const res = await apiFetch<{
        audit_result: { audit_status: string; audit_notes: string; promoted_to_company: boolean };
        company: CompanyDetail;
      }>(`/api/industry-structure/companies/${detailCompany.company_id}/classifications`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dimension: clsDimension,
          classification: clsValue,
          valid_from: clsValidFrom,
          valid_to: clsValidTo || null,
          official_source_id: clsSourceId ? Number(clsSourceId) : null,
          source_url: clsSourceUrl.trim() || null,
          evidence: clsEvidence.trim(),
        }),
      });
      setClsAuditFeedback(res.audit_result);
      setDetailCompany(res.company);
      if (res.audit_result.audit_status === "VERIFIED") {
        setClsEvidence("");
        setClsSourceUrl("");
      }
      await Promise.all([loadCompanies(), loadReferenceData()]);
    } catch (err: unknown) {
      setClsAuditFeedback({
        audit_status: "ERROR",
        audit_notes: err instanceof Error ? err.message : "Error registrando evidencia.",
        promoted_to_company: false,
      });
    } finally {
      setClsSubmitting(false);
    }
  };

  const hasActiveFilters =
    selectedSizes.length > 0 ||
    selectedOrigins.length > 0 ||
    selectedModels.length > 0 ||
    selectedChains.length > 0 ||
    searchText.trim().length > 0;

  const filterQs = buildFilterQueryString();
  const researchLinkHref = `/research${filterQs ? `?${filterQs}` : ""}`;

  const dimA = taxonomy?.dimensions.find((d) => d.key === "SIZE");
  const dimB = taxonomy?.dimensions.find((d) => d.key === "ORIGIN");
  const dimC = taxonomy?.dimensions.find((d) => d.key === "PRODUCTION_MODEL");
  const dimD = taxonomy?.dimensions.find((d) => d.key === "CHAIN_POSITION");

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-0.5 text-xs font-semibold uppercase tracking-wide text-indigo-800">
            <Building2 className="h-3.5 w-3.5" />
            Módulo Experimental · Dimensiones Independientes
          </div>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">
            Estructura de la industria
          </h1>
          <p className="mt-1 text-sm leading-relaxed text-slate-600">
            Módulo experimental para estudiar la estructura empresarial del complejo textil e indumentaria argentino sin mezclar{" "}
            <strong className="font-semibold text-slate-800">tamaño</strong>,{" "}
            <strong className="font-semibold text-slate-800">origen</strong>,{" "}
            <strong className="font-semibold text-slate-800">modelo productivo</strong> ni{" "}
            <strong className="font-semibold text-slate-800">posición en la cadena</strong> en una única etiqueta.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setRegMessage(null);
              setShowRegisterModal(true);
            }}
            className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-4 py-2 text-xs font-semibold text-white hover:bg-navy/90"
          >
            <Plus className="h-4 w-4" />
            Registrar firma / evidencia oficial
          </button>
          <Link
            href={researchLinkHref}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-800 hover:border-navy hover:text-navy"
          >
            <FlaskConical className="h-4 w-4" />
            Construir pregunta en Research
          </Link>
        </div>
      </div>

      {/* Strict Official-Source & Anti-Conflation Guardrail */}
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs leading-relaxed text-amber-950">
          <div className="flex items-center gap-1.5 font-semibold text-amber-900">
            <ShieldAlert className="h-4 w-4 shrink-0" />
            Regla estricta de fuentes verificables (sin inferencia)
          </div>
          <p className="mt-1.5">
            Toda clasificación empresarial distinta de <code className="rounded bg-amber-100 px-1 font-mono font-semibold">UNKNOWN</code>{" "}
            exige una fuente oficial aprobada (<code className="font-mono">official_sources</code>), URL de dominio oficial y evidencia documental verificable.
            Si no existe evidencia suficiente, la dimensión permanece en <code className="rounded bg-amber-100 px-1 font-mono font-semibold">UNKNOWN</code> (No determinado).
          </p>
          <p className="mt-1.5 text-[11px] text-amber-900">
            <strong>Prohibido inferir desde:</strong> noticias, redes sociales, sitios web comerciales, Wikipedia, conocimiento del modelo o percepción del tamaño de la marca.
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs leading-relaxed text-slate-700">
          <div className="flex items-center gap-1.5 font-semibold text-navy">
            <Info className="h-4 w-4 shrink-0" />
            Principio metodológico: ortogonalidad de dimensiones y no causalidad
          </div>
          <p className="mt-1.5">
            Una empresa grande de capital nacional puede importar producto terminado, mientras una firma de capital extranjero puede producir localmente o una PyME nacional puede operar en confección con insumos importados.
            Cada dimensión se audita y filtra por separado, preservando su historial temporal (<code className="font-mono">valid_from</code> / <code className="font-mono">valid_to</code>).
            Las asociaciones entre estructura empresarial y series agregadas <strong>no implican causalidad</strong>.
          </p>
        </div>
      </section>

      {/* Summary KPIs */}
      {summary && (
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Firmas registradas</p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-900">{summary.total_companies}</p>
            <p className="mt-0.5 text-[11px] text-slate-500">Sin clasificaciones fabricadas</p>
          </div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-emerald-800">Verificadas (4/4)</p>
            <p className="mt-1 font-mono text-2xl font-bold text-emerald-900">
              {summary.classification_status_counts.VERIFIED_COMPLETE}
            </p>
            <p className="mt-0.5 text-[11px] text-emerald-800">Todas las dimensiones con evidencia</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-800">Parciales</p>
            <p className="mt-1 font-mono text-2xl font-bold text-amber-900">
              {summary.classification_status_counts.PARTIALLY_VERIFIED}
            </p>
            <p className="mt-0.5 text-[11px] text-amber-800">Resto explícitamente UNKNOWN</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">No determinadas</p>
            <p className="mt-1 font-mono text-2xl font-bold text-slate-800">
              {summary.classification_status_counts.UNKNOWN}
            </p>
            <p className="mt-0.5 text-[11px] text-slate-500">En espera de evidencia oficial</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Auditoría historial</p>
            <p className="mt-1 font-mono text-lg font-bold text-slate-900">
              <span className="text-emerald-700">{summary.audit_history_counts.VERIFIED}</span>{" "}
              <span className="text-xs font-normal text-slate-400">VERIFIED</span> /{" "}
              <span className="text-crimson">{summary.audit_history_counts.REJECTED}</span>{" "}
              <span className="text-xs font-normal text-slate-400">REJECTED</span>
            </p>
            <p className="mt-0.5 text-[11px] text-slate-500">Regla de fuentes aplicada</p>
          </div>
        </section>
      )}

      {/* Combinable 4-Dimension Filter Panel */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-navy" />
            <h2 className="text-base font-semibold text-slate-900">
              Filtros combinables por dimensión independiente
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              >
                <X className="h-3.5 w-3.5" />
                Limpiar filtros
              </button>
            )}
            <a
              href={`/api/industry-structure/export?format=csv${filterQs ? `&${filterQs}` : ""}`}
              download
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-navy hover:text-navy"
            >
              <Download className="h-3.5 w-3.5" />
              CSV
            </a>
            <a
              href={`/api/industry-structure/export?format=json${filterQs ? `&${filterQs}` : ""}`}
              download
              className="inline-flex items-center gap-1 rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700 hover:border-navy hover:text-navy"
            >
              <Download className="h-3.5 w-3.5" />
              JSON
            </a>
          </div>
        </div>

        {/* Search input + Example combinations */}
        <div className="mt-4 space-y-3">
          <div className="relative max-w-md">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Buscar por razón social, marca o CUIT..."
              className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-xs text-slate-900 focus:border-navy focus:outline-none"
            />
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Combinaciones ejemplo:
            </span>
            {COMBINED_EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => applyPresetExample(ex)}
                className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] font-medium text-slate-700 transition hover:border-navy hover:bg-white hover:text-navy"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* 4 Independent Dimension Filter Grids */}
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          {/* Dimension A: Tamaño */}
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-navy">
                Dimensión A · Tamaño
              </h3>
              <span className="text-[11px] text-slate-500">Criterio MiPyME oficial</span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => toggleItem(setSelectedSizes, "PYME")}
                className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                  selectedSizes.includes("PYME")
                    ? "border-navy bg-navy text-white"
                    : "border-indigo-200 bg-indigo-50 text-indigo-900 hover:border-navy"
                }`}
              >
                PyME (Micro + Pequeña + Mediana)
              </button>
              {(dimA?.options ?? []).map((opt) => {
                const active = selectedSizes.includes(opt.code);
                const count = summary?.dimensions.SIZE.find((x) => x.code === opt.code)?.count ?? 0;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    onClick={() => toggleItem(setSelectedSizes, opt.code)}
                    className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      active
                        ? "border-navy bg-navy text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:border-navy"
                    }`}
                  >
                    {opt.label}{" "}
                    <span className={`font-mono text-[10px] ${active ? "text-slate-200" : "text-slate-400"}`}>
                      ({count})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Dimension B: Origen */}
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-navy">
                Dimensión B · Origen
              </h3>
              <span className="text-[11px] text-slate-500">Capital societario verificado</span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {(dimB?.options ?? []).map((opt) => {
                const active = selectedOrigins.includes(opt.code);
                const count = summary?.dimensions.ORIGIN.find((x) => x.code === opt.code)?.count ?? 0;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    onClick={() => toggleItem(setSelectedOrigins, opt.code)}
                    className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      active
                        ? "border-navy bg-navy text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:border-navy"
                    }`}
                  >
                    {opt.label}{" "}
                    <span className={`font-mono text-[10px] ${active ? "text-slate-200" : "text-slate-400"}`}>
                      ({count})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Dimension C: Modelo productivo */}
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-navy">
                Dimensión C · Modelo productivo
              </h3>
              <span className="text-[11px] text-slate-500">Independiente de origen y tamaño</span>
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {(dimC?.options ?? []).map((opt) => {
                const active = selectedModels.includes(opt.code);
                const count =
                  summary?.dimensions.PRODUCTION_MODEL.find((x) => x.code === opt.code)?.count ?? 0;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    onClick={() => toggleItem(setSelectedModels, opt.code)}
                    className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      active
                        ? "border-navy bg-navy text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:border-navy"
                    }`}
                  >
                    {opt.label}{" "}
                    <span className={`font-mono text-[10px] ${active ? "text-slate-200" : "text-slate-400"}`}>
                      ({count})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Dimension D: Posición en la cadena */}
          <div className="rounded-lg border border-slate-200 bg-slate-50/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-navy">
                Dimensión D · Posición en la cadena (múltiple)
              </h3>
              {selectedChains.length > 1 && (
                <div className="inline-flex rounded border border-slate-200 bg-white text-[11px]">
                  <button
                    type="button"
                    onClick={() => setChainMatch("any")}
                    className={`px-2 py-0.5 font-medium ${
                      chainMatch === "any" ? "bg-navy text-white" : "text-slate-600"
                    }`}
                  >
                    Cualquiera (OR)
                  </button>
                  <button
                    type="button"
                    onClick={() => setChainMatch("all")}
                    className={`px-2 py-0.5 font-medium ${
                      chainMatch === "all" ? "bg-navy text-white" : "text-slate-600"
                    }`}
                  >
                    Todas (AND)
                  </button>
                </div>
              )}
            </div>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {(dimD?.options ?? []).map((opt) => {
                const active = selectedChains.includes(opt.code);
                const count =
                  summary?.dimensions.CHAIN_POSITION.find((x) => x.code === opt.code)?.count ?? 0;
                return (
                  <button
                    key={opt.code}
                    type="button"
                    onClick={() => toggleItem(setSelectedChains, opt.code)}
                    className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                      active
                        ? "border-teal bg-teal text-white"
                        : "border-slate-200 bg-white text-slate-700 hover:border-teal"
                    }`}
                  >
                    {opt.label}{" "}
                    <span className={`font-mono text-[10px] ${active ? "text-emerald-100" : "text-slate-400"}`}>
                      ({count})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-crimson">
          {error}
        </div>
      )}

      {/* Results Table */}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Registro auditado de empresas ({companiesResp?.count ?? 0})
            </h2>
            <p className="text-xs text-slate-500">
              Cada columna corresponde a una dimensión independiente respaldada en <code className="font-mono">company_classification_history</code>.
            </p>
          </div>
          {hasActiveFilters && (
            <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-800">
              Filtros combinados activos
            </span>
          )}
        </div>

        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">Cargando registro empresarial...</div>
        ) : !companiesResp || companiesResp.items.length === 0 ? (
          <div className="p-10 text-center">
            <Building2 className="mx-auto h-8 w-8 text-slate-300" />
            <h3 className="mt-3 text-sm font-semibold text-slate-900">
              {summary && summary.total_companies === 0
                ? "Aún no hay firmas cargadas con evidencia oficial"
                : "Ninguna empresa coincide con la combinación de filtros seleccionada"}
            </h3>
            <p className="mx-auto mt-1.5 max-w-xl text-xs leading-relaxed text-slate-600">
              {summary && summary.total_companies === 0
                ? "Por regla estricta de fuentes, Datos de Industria Textil Argentina (DITA) no precarga clasificaciones inferidas desde conocimiento del modelo, prensa, redes sociales, webs comerciales ni Wikipedia. Puedes registrar firmas (inician en UNKNOWN) y auditar evidencia documental oficial (CNV, Boletín Oficial, Registro MiPyME, ARCA/AFIP, IGJ o RIN)."
                : "Prueba flexibilizar alguno de los filtros de Tamaño, Origen, Modelo productivo o Posición en la cadena, o limpiar todos los filtros."}
            </p>
            <div className="mt-4 flex justify-center gap-2">
              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Limpiar filtros
                </button>
              )}
              <button
                type="button"
                onClick={() => setShowRegisterModal(true)}
                className="inline-flex items-center gap-1.5 rounded-lg bg-navy px-3.5 py-2 text-xs font-semibold text-white hover:bg-navy/90"
              >
                <Plus className="h-3.5 w-3.5" />
                Registrar firma
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">Razón social / Marca</th>
                  <th className="px-4 py-3">Dim. A · Tamaño</th>
                  <th className="px-4 py-3">Dim. B · Origen</th>
                  <th className="px-4 py-3">Dim. C · Modelo productivo</th>
                  <th className="px-4 py-3">Dim. D · Cadena</th>
                  <th className="px-4 py-3">Estado</th>
                  <th className="px-4 py-3 text-right">Evidencia</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {companiesResp.items.map((c: CompanyItem) => (
                  <tr key={c.company_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-900">{c.legal_name}</div>
                      <div className="text-[11px] text-slate-500">
                        {c.brand_name ? `Marca: ${c.brand_name}` : "Sin marca declarada"}
                        {c.cuit ? ` · CUIT ${c.cuit}` : ""}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${badgeClassForCode(
                          c.company_size
                        )}`}
                      >
                        {c.company_size_label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${badgeClassForCode(
                          c.company_origin
                        )}`}
                      >
                        {c.company_origin_label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${badgeClassForCode(
                          c.production_model
                        )}`}
                      >
                        {c.production_model_label}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {c.chain_positions.map((pos, i) => (
                          <span
                            key={pos}
                            className={`inline-flex rounded border px-1.5 py-0.5 text-[11px] font-medium ${badgeClassForCode(
                              pos
                            )}`}
                          >
                            {c.chain_position_labels[i] ?? pos}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-semibold ${badgeClassForCode(
                          c.classification_status
                        )}`}
                      >
                        {c.classification_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => openCompanyDetail(c.company_id)}
                        className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-navy hover:border-navy"
                      >
                        <History className="h-3.5 w-3.5" />
                        Historial y auditar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Official Criteria Reference */}
      {taxonomy && (
        <section className="rounded-xl border border-slate-200 bg-white p-6">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-navy" />
            <h2 className="text-base font-semibold text-slate-900">
              Criterios oficiales verificables por dimensión
            </h2>
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {taxonomy.dimensions.map((d) => (
              <div key={d.key} className="rounded-lg border border-slate-200 bg-slate-50/60 p-4 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-navy">
                    Dimensión {d.letter}: {d.name}
                  </span>
                  {d.multi_valued && (
                    <span className="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
                      Multi-posición
                    </span>
                  )}
                </div>
                <p className="mt-1.5 leading-relaxed text-slate-600">{d.official_criteria}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Modal: Register New Company */}
      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h2 className="text-base font-semibold text-slate-900">Registrar firma empresarial</h2>
              <button
                type="button"
                onClick={() => setShowRegisterModal(false)}
                className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              Toda empresa recién registrada inicia automáticamente con{" "}
              <code className="font-mono font-semibold text-slate-900">UNKNOWN</code> en Tamaño, Origen,
              Modelo productivo y Posición en la cadena. Las clasificaciones solo cambian al aprobarse evidencia
              oficial verificable.
            </p>

            <form onSubmit={handleRegisterCompany} className="mt-4 space-y-3 text-xs">
              <label className="block">
                <span className="font-semibold text-slate-700">Razón social (legal_name) *</span>
                <input
                  type="text"
                  required
                  value={regLegalName}
                  onChange={(e) => setRegLegalName(e.target.value)}
                  placeholder="Ej: Hilandería Ejemplo S.A."
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-navy focus:outline-none"
                />
              </label>

              <label className="block">
                <span className="font-semibold text-slate-700">Marca comercial (brand_name)</span>
                <input
                  type="text"
                  value={regBrandName}
                  onChange={(e) => setRegBrandName(e.target.value)}
                  placeholder="Opcional"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-navy focus:outline-none"
                />
              </label>

              <label className="block">
                <span className="font-semibold text-slate-700">CUIT (opcional)</span>
                <input
                  type="text"
                  value={regCuit}
                  onChange={(e) => setRegCuit(e.target.value)}
                  placeholder="Ej: 30-12345678-9"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-navy focus:outline-none"
                />
              </label>

              <label className="block">
                <span className="font-semibold text-slate-700">Notas metodológicas</span>
                <textarea
                  rows={2}
                  value={regNotes}
                  onChange={(e) => setRegNotes(e.target.value)}
                  placeholder="Referencias iniciales o notas sobre cobertura documental..."
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-navy focus:outline-none"
                />
              </label>

              {regMessage && <p className="font-medium text-crimson">{regMessage}</p>}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowRegisterModal(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={regSubmitting}
                  className="rounded-lg bg-navy px-4 py-2 font-semibold text-white hover:bg-navy/90 disabled:opacity-50"
                >
                  {regSubmitting ? "Registrando..." : "Crear en estado UNKNOWN"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Company Detail + Audited Classification History + Add Official Evidence */}
      {(detailCompany || loadingDetail) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl border border-slate-200 bg-white p-6 shadow-xl">
            {loadingDetail || !detailCompany ? (
              <div className="p-8 text-center text-sm text-slate-500">Cargando historial de auditoría...</div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-start justify-between gap-4 border-b border-slate-200 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">{detailCompany.legal_name}</h2>
                    <p className="text-xs text-slate-500">
                      {detailCompany.brand_name ? `Marca: ${detailCompany.brand_name} · ` : ""}
                      {detailCompany.cuit ? `CUIT ${detailCompany.cuit} · ` : ""}
                      Estado: <strong>{detailCompany.classification_status_label}</strong>
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setDetailCompany(null)}
                    className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Current 4 Independent Dimensions */}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs">
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <span className="text-[10px] font-semibold uppercase text-slate-500">Dim. A · Tamaño</span>
                    <p className="mt-1 font-semibold text-slate-900">{detailCompany.company_size_label}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <span className="text-[10px] font-semibold uppercase text-slate-500">Dim. B · Origen</span>
                    <p className="mt-1 font-semibold text-slate-900">{detailCompany.company_origin_label}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <span className="text-[10px] font-semibold uppercase text-slate-500">
                      Dim. C · Modelo productivo
                    </span>
                    <p className="mt-1 font-semibold text-slate-900">{detailCompany.production_model_label}</p>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <span className="text-[10px] font-semibold uppercase text-slate-500">
                      Dim. D · Posición en cadena
                    </span>
                    <p className="mt-1 font-semibold text-slate-900">
                      {detailCompany.chain_position_labels.join(", ")}
                    </p>
                  </div>
                </div>

                {/* Add Official Evidence Form */}
                <form
                  onSubmit={handleSubmitClassification}
                  className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 text-xs space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-900">
                      Aportar clasificación con evidencia oficial verificable (Company Auditor)
                    </h3>
                    <span className="text-[11px] text-slate-500">
                      Fuentes no oficiales serán marcadas REJECTED automáticamente
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    <label className="block">
                      <span className="font-medium text-slate-700">Dimensión *</span>
                      <select
                        value={clsDimension}
                        onChange={(e) =>
                          setClsDimension(
                            e.target.value as "SIZE" | "ORIGIN" | "PRODUCTION_MODEL" | "CHAIN_POSITION"
                          )
                        }
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      >
                        <option value="SIZE">A · Tamaño</option>
                        <option value="ORIGIN">B · Origen</option>
                        <option value="PRODUCTION_MODEL">C · Modelo productivo</option>
                        <option value="CHAIN_POSITION">D · Posición en la cadena</option>
                      </select>
                    </label>

                    <label className="block">
                      <span className="font-medium text-slate-700">Clasificación *</span>
                      <select
                        value={clsValue}
                        onChange={(e) => setClsValue(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      >
                        {currentDimOptions.map((o) => (
                          <option key={o.code} value={o.code}>
                            {o.label} ({o.code})
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="font-medium text-slate-700">Vigente desde (valid_from) *</span>
                      <input
                        type="date"
                        required
                        value={clsValidFrom}
                        onChange={(e) => setClsValidFrom(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      />
                    </label>

                    <label className="block">
                      <span className="font-medium text-slate-700">Vigente hasta (valid_to)</span>
                      <input
                        type="date"
                        value={clsValidTo}
                        onChange={(e) => setClsValidTo(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      />
                    </label>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="font-medium text-slate-700">
                        Organismo oficial (official_source_id) {clsValue !== "UNKNOWN" ? "*" : ""}
                      </span>
                      <select
                        value={clsSourceId}
                        onChange={(e) => setClsSourceId(e.target.value)}
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      >
                        <option value="">-- Seleccionar fuente oficial aprobada --</option>
                        {(summary?.approved_official_sources ?? []).map((src) => (
                          <option key={src.official_source_id} value={src.official_source_id}>
                            [{src.source_code}] {src.institution} ({src.official_domain})
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block">
                      <span className="font-medium text-slate-700">
                        URL del documento oficial (source_url) {clsValue !== "UNKNOWN" ? "*" : ""}
                      </span>
                      <input
                        type="url"
                        value={clsSourceUrl}
                        onChange={(e) => setClsSourceUrl(e.target.value)}
                        placeholder="https://www.cnv.gov.ar/... o https://www.boletinoficial.gob.ar/..."
                        className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                      />
                    </label>
                  </div>

                  <label className="block">
                    <span className="font-medium text-slate-700">
                      Evidencia documental verificable (evidence) *
                    </span>
                    <textarea
                      required
                      rows={2}
                      value={clsEvidence}
                      onChange={(e) => setClsEvidence(e.target.value)}
                      placeholder="Ej: Constancia Certificado MiPyME vigente Res. SEPyME 220/2019 (Tramo Pequeña Industria) / Memoria Anual ejercicio 2025 presentada ante CNV AIF."
                      className="mt-1 w-full rounded border border-slate-300 bg-white px-2.5 py-1.5"
                    />
                  </label>

                  {clsAuditFeedback && (
                    <div
                      className={`rounded-lg border p-3 text-xs ${
                        clsAuditFeedback.audit_status === "VERIFIED"
                          ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                          : "border-red-200 bg-red-50 text-crimson"
                      }`}
                    >
                      <div className="flex items-center gap-1.5 font-semibold">
                        {clsAuditFeedback.audit_status === "VERIFIED" ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <AlertTriangle className="h-4 w-4" />
                        )}
                        Resultado auditoría: {clsAuditFeedback.audit_status}
                      </div>
                      <p className="mt-1">{clsAuditFeedback.audit_notes}</p>
                    </div>
                  )}

                  <div className="flex justify-end">
                    <button
                      type="submit"
                      disabled={clsSubmitting}
                      className="rounded-lg bg-navy px-4 py-2 font-semibold text-white hover:bg-navy/90 disabled:opacity-50"
                    >
                      {clsSubmitting ? "Auditando evidencia..." : "Auditar y registrar en historial"}
                    </button>
                  </div>
                </form>

                {/* Full Audit History Table */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Historial de clasificaciones (`company_classification_history`) —{" "}
                    {detailCompany.classification_history.length} registros
                  </h3>
                  {detailCompany.classification_history.length === 0 ? (
                    <p className="mt-2 text-xs text-slate-500">
                      Aún no existen registros de evidencia en el historial; todas las dimensiones permanecen en UNKNOWN.
                    </p>
                  ) : (
                    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-200">
                      <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
                        <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-600">
                          <tr>
                            <th className="px-3 py-2">Dimensión</th>
                            <th className="px-3 py-2">Clasificación</th>
                            <th className="px-3 py-2">Vigencia</th>
                            <th className="px-3 py-2">Fuente oficial</th>
                            <th className="px-3 py-2">Evidencia y notas de auditoría</th>
                            <th className="px-3 py-2">Estado</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {detailCompany.classification_history.map((h) => (
                            <tr key={h.history_id}>
                              <td className="px-3 py-2 font-mono text-[11px] font-semibold text-slate-700">
                                {h.dimension}
                              </td>
                              <td className="px-3 py-2 font-medium text-slate-900">
                                {h.classification_label}
                              </td>
                              <td className="px-3 py-2 font-mono text-[11px] text-slate-600">
                                {formatDateShort(h.valid_from)} → {h.valid_to ? formatDateShort(h.valid_to) : "Vigente"}
                              </td>
                              <td className="px-3 py-2 text-[11px]">
                                {h.official_source_code ? (
                                  <div>
                                    <span className="font-semibold text-slate-800">{h.official_source_code}</span>
                                    {h.source_url && (
                                      <a
                                        href={h.source_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="mt-0.5 flex items-center gap-1 text-navy hover:underline"
                                      >
                                        Fuente <ExternalLink className="h-3 w-3" />
                                      </a>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-slate-400">—</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-[11px] text-slate-700">
                                <p>{h.evidence}</p>
                                {h.audit_notes && (
                                  <p className="mt-1 text-[10px] text-slate-500">{h.audit_notes}</p>
                                )}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  className={`inline-flex rounded border px-2 py-0.5 text-[10px] font-semibold ${badgeClassForCode(
                                    h.audit_status
                                  )}`}
                                >
                                  {h.audit_status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function EstructuraIndustriaPage() {
  return (
    <Suspense
      fallback={<div className="p-8 text-sm text-slate-500">Cargando Estructura de la industria...</div>}
    >
      <IndustryStructureContent />
    </Suspense>
  );
}
