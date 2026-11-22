import type {
  CategorySummary,
  CompaniesListResponse,
  CompanyClassificationHistoryItem,
  CompanyDetail,
  CompanyItem,
  CompareResponse,
  GlossaryItem,
  IndustryStructureSummary,
  IndustryTaxonomy,
  ObservationPoint,
  ResearchSuggestion,
  SearchResultItem,
  SeriesCard,
  SeriesDetail,
  SeriesObservationsResponse,
  StructuralResearchFrame,
  StructuralResearchPreset,
  TraceabilityResponse,
} from "./types";

interface SnapshotData {
  health: Record<string, unknown>;
  categories: CategorySummary[];
  series_list: SeriesCard[];
  series_detail: Record<string, SeriesDetail>;
  series_traceability: Record<string, TraceabilityResponse>;
  series_observations_raw: Record<
    string,
    {
      observations: ObservationPoint[];
      revisions_history: SeriesObservationsResponse["revisions_history"];
    }
  >;
  trade_chain: Record<string, unknown>;
  glossary: GlossaryItem[];
  sources: Array<Record<string, unknown>>;
  updates: Array<Record<string, unknown>>;
  auditor_summary: Record<string, unknown>;
  auditor_series: Array<Record<string, unknown>>;
  industry_taxonomy: IndustryTaxonomy;
  industry_summary: IndustryStructureSummary;
  industry_companies: CompanyDetail[];
  industry_presets: StructuralResearchPreset[];
}

let cachedSnapshot: SnapshotData | null = null;
let snapshotPromise: Promise<SnapshotData> | null = null;

const LOCAL_COMPANIES_KEY = "tdh_verified_companies_v1";

async function getSnapshot(): Promise<SnapshotData> {
  if (cachedSnapshot) return cachedSnapshot;
  if (!snapshotPromise) {
    snapshotPromise = fetch("/data/verified_db_snapshot.json", { cache: "force-cache" })
      .then((r) => {
        if (!r.ok) throw new Error(`No se pudo cargar snapshot (${r.status})`);
        return r.json() as Promise<SnapshotData>;
      })
      .then((data) => {
        cachedSnapshot = data;
        return data;
      });
  }
  return snapshotPromise;
}

function getStoredCompanies(snap: SnapshotData): CompanyDetail[] {
  if (typeof window === "undefined") return snap.industry_companies;
  try {
    const raw = window.localStorage.getItem(LOCAL_COMPANIES_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as CompanyDetail[];
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch {
    // ignore storage error
  }
  return snap.industry_companies;
}

function saveStoredCompanies(companies: CompanyDetail[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCAL_COMPANIES_KEY, JSON.stringify(companies));
  } catch {
    // ignore storage error
  }
}

function normalizeText(str: string): string {
  return str
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function monthDiff(d1Iso: string, d2Iso: string): number {
  const [y1, m1] = d1Iso.slice(0, 10).split("-").map(Number);
  const [y2, m2] = d2Iso.slice(0, 10).split("-").map(Number);
  return (y2 - y1) * 12 + (m2 - m1);
}

function aggregateDailyToMonthly(
  pts: ObservationPoint[],
  method: "avg" | "eop" = "avg"
): ObservationPoint[] {
  const byMonth = new Map<string, ObservationPoint[]>();
  for (const p of pts) {
    const ym = `${p.date.slice(0, 7)}-01`;
    const arr = byMonth.get(ym) || [];
    arr.push(p);
    byMonth.set(ym, arr);
  }
  const out: ObservationPoint[] = [];
  for (const [ym, group] of Array.from(byMonth.entries()).sort((a, b) => a[0].localeCompare(b[0]))) {
    if (method === "eop") {
      const last = group[group.length - 1];
      out.push({ ...last, date: ym });
    } else {
      const avg = group.reduce((acc, x) => acc + x.value, 0) / group.length;
      out.push({
        date: ym,
        value: Number(avg.toFixed(4)),
        is_preliminary: group.some((g) => g.is_preliminary),
        is_outlier_flagged: group.some((g) => g.is_outlier_flagged),
        revision_number: Math.max(...group.map((g) => g.revision_number)),
      });
    }
  }
  return out;
}

function transformPoints(
  pts: ObservationPoint[],
  frequency: string,
  transform: string,
  baseDate?: string | null
): {
  rows: ObservationPoint[];
  meta: { transform: string; warnings: string[]; base_date_used?: string; base_value_used?: number };
} {
  const warnings: string[] = [];
  if (transform === "level" || transform === "original") {
    return { rows: pts.map((p) => ({ ...p })), meta: { transform: "level", warnings } };
  }

  if (transform === "mom_pct" || transform === "pct_change") {
    const out: ObservationPoint[] = [];
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1];
      const curr = pts[i];
      if (frequency === "MONTHLY" && monthDiff(prev.date, curr.date) !== 1) continue;
      if (frequency === "QUARTERLY" && monthDiff(prev.date, curr.date) !== 3) continue;
      if (Math.abs(prev.value) < 1e-9) continue;
      const pct = ((curr.value - prev.value) / Math.abs(prev.value)) * 100;
      out.push({ ...curr, raw_value: curr.value, value: Number(pct.toFixed(2)) });
    }
    return { rows: out, meta: { transform: "mom_pct", warnings } };
  }

  if (transform === "yoy_pct") {
    const byDate = new Map(pts.map((p) => [p.date, p]));
    const out: ObservationPoint[] = [];
    for (const curr of pts) {
      const [y, m, d] = curr.date.split("-").map(Number);
      const prevIso = `${y - 1}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      const prev = byDate.get(prevIso);
      if (!prev || Math.abs(prev.value) < 1e-9) continue;
      const pct = ((curr.value - prev.value) / Math.abs(prev.value)) * 100;
      out.push({ ...curr, raw_value: curr.value, value: Number(pct.toFixed(2)) });
    }
    return { rows: out, meta: { transform: "yoy_pct", warnings } };
  }

  // base_100
  if (pts.some((p) => p.value <= 0)) {
    warnings.push("La serie contiene valores nulos o negativos; el índice Base 100 debe interpretarse con precaución.");
  }
  let ref = pts[0];
  if (baseDate) {
    const candidate = pts.find((p) => p.date >= baseDate);
    if (candidate) ref = candidate;
  }
  if (!ref || Math.abs(ref.value) < 1e-9) {
    return { rows: [], meta: { transform: "base_100", warnings } };
  }
  const rows = pts.map((p) => ({
    ...p,
    raw_value: p.value,
    value: Number(((p.value / ref.value) * 100).toFixed(2)),
  }));
  return {
    rows,
    meta: {
      transform: "base_100",
      warnings,
      base_date_used: ref.date,
      base_value_used: ref.value,
    },
  };
}

const FORBIDDEN_DOMAINS = [
  "wikipedia.org",
  "wikimedia.org",
  "instagram.com",
  "facebook.com",
  "twitter.com",
  "x.com",
  "linkedin.com",
  "tiktok.com",
  "youtube.com",
  "infobae.com",
  "clarin.com",
  "lanacion.com.ar",
  "ambito.com",
  "cronista.com",
  "iprofesional.com",
  "pagina12.com.ar",
  "perfil.com",
];

function recomputeSummary(
  baseSummary: IndustryStructureSummary,
  companies: CompanyDetail[]
): IndustryStructureSummary {
  const statusCounts = { VERIFIED_COMPLETE: 0, PARTIALLY_VERIFIED: 0, UNKNOWN: 0 };
  const histCounts = { VERIFIED: 0, REJECTED: 0, PENDING: 0, WARNING: 0 };

  for (const c of companies) {
    if (c.classification_status === "VERIFIED_COMPLETE") statusCounts.VERIFIED_COMPLETE++;
    else if (c.classification_status === "PARTIALLY_VERIFIED") statusCounts.PARTIALLY_VERIFIED++;
    else statusCounts.UNKNOWN++;

    for (const h of c.classification_history || []) {
      if (h.audit_status === "VERIFIED") histCounts.VERIFIED++;
      else if (h.audit_status === "REJECTED") histCounts.REJECTED++;
      else if (h.audit_status === "WARNING") histCounts.WARNING++;
      else histCounts.PENDING++;
    }
  }

  return {
    ...baseSummary,
    total_companies: companies.length,
    classification_status_counts: statusCounts,
    audit_history_counts: histCounts,
    dimensions: {
      SIZE: baseSummary.dimensions.SIZE.map((d) => ({
        ...d,
        count: companies.filter((c) => c.company_size === d.code).length,
      })),
      ORIGIN: baseSummary.dimensions.ORIGIN.map((d) => ({
        ...d,
        count: companies.filter((c) => c.company_origin === d.code).length,
      })),
      PRODUCTION_MODEL: baseSummary.dimensions.PRODUCTION_MODEL.map((d) => ({
        ...d,
        count: companies.filter((c) => c.production_model === d.code).length,
      })),
      CHAIN_POSITION: baseSummary.dimensions.CHAIN_POSITION.map((d) => ({
        ...d,
        count: companies.filter((c) => c.chain_positions.includes(d.code)).length,
      })),
    },
  };
}

function filterCompaniesList(
  companies: CompanyDetail[],
  params: {
    sizes?: string[];
    origins?: string[];
    models?: string[];
    chains?: string[];
    chainMatch?: string;
    q?: string | null;
  }
): CompanyDetail[] {
  const expSizes: string[] = [];
  for (const s of params.sizes || []) {
    const up = s.toUpperCase();
    if (up === "PYME") expSizes.push("MICRO", "SMALL", "MEDIUM");
    else if (up) expSizes.push(up);
  }
  const origins = (params.origins || []).map((x) => x.toUpperCase()).filter(Boolean);
  const models = (params.models || []).map((x) => x.toUpperCase()).filter(Boolean);
  const chains = (params.chains || []).map((x) => x.toUpperCase()).filter(Boolean);
  const qNorm = params.q ? params.q.trim().toLowerCase() : "";

  return companies.filter((c) => {
    if (expSizes.length > 0 && !expSizes.includes(c.company_size)) return false;
    if (origins.length > 0 && !origins.includes(c.company_origin)) return false;
    if (models.length > 0 && !models.includes(c.production_model)) return false;
    if (chains.length > 0) {
      if (params.chainMatch === "all") {
        if (!chains.every((pos) => c.chain_positions.includes(pos))) return false;
      } else {
        if (!chains.some((pos) => c.chain_positions.includes(pos))) return false;
      }
    }
    if (qNorm) {
      const hay = `${c.legal_name} ${c.brand_name || ""} ${c.cuit || ""}`.toLowerCase();
      if (!hay.includes(qNorm)) return false;
    }
    return true;
  });
}

export async function standaloneApiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const snap = await getSnapshot();
  const url = new URL(path, "http://localhost");
  const pathname = url.pathname;
  const sp = url.searchParams;
  const method = (init?.method || "GET").toUpperCase();

  if (pathname === "/api/health") return snap.health as T;
  if (pathname === "/api/categories") return snap.categories as T;

  if (pathname === "/api/series") {
    const cat = sp.get("category");
    const sType = sp.get("series_type");
    let list = snap.series_list;
    if (cat) list = list.filter((s) => s.category === cat);
    if (sType) list = list.filter((s) => s.series_type === sType.toUpperCase());
    return list as T;
  }

  const obsMatch = pathname.match(/^\/api\/series\/([^/]+)\/observations$/);
  if (obsMatch) {
    const code = decodeURIComponent(obsMatch[1]);
    const detail = snap.series_detail[code];
    const rawEntry = snap.series_observations_raw[code];
    if (!detail || !rawEntry) throw new Error(`Serie '${code}' no encontrada.`);

    const transform = sp.get("transform") || "level";
    const startDate = sp.get("start_date");
    const endDate = sp.get("end_date");
    let baseDate = sp.get("base_date");
    if (transform === "base_100" && !baseDate && startDate) {
      baseDate = startDate;
    }
    const { rows, meta } = transformPoints(rawEntry.observations, detail.frequency, transform, baseDate);
    const filtered = rows.filter(
      (r) => (!startDate || r.date >= startDate) && (!endDate || r.date <= endDate)
    );
    const resp: SeriesObservationsResponse = {
      series_code: detail.series_code,
      series_name: detail.series_name,
      unit: detail.unit,
      frequency: detail.frequency,
      transform,
      meta,
      count: filtered.length,
      observations: filtered,
      revisions_history: rawEntry.revisions_history || [],
    };
    return resp as T;
  }

  const traceMatch = pathname.match(/^\/api\/series\/([^/]+)\/traceability$/);
  if (traceMatch) {
    const code = decodeURIComponent(traceMatch[1]);
    const tr = snap.series_traceability[code];
    if (!tr) throw new Error(`Trazabilidad de '${code}' no encontrada.`);
    return tr as T;
  }

  const detailMatch = pathname.match(/^\/api\/series\/([^/]+)(?:\/metadata)?$/);
  if (detailMatch) {
    const code = decodeURIComponent(detailMatch[1]);
    const det = snap.series_detail[code];
    if (!det) throw new Error(`Serie '${code}' no encontrada.`);
    return det as T;
  }

  if (pathname === "/api/search") {
    const q = normalizeText(sp.get("q") || "");
    const tokens = q.split(" ").filter((t) => t.length >= 2);
    const results: SearchResultItem[] = [];
    for (const s of snap.series_list) {
      const hay = normalizeText(
        `${s.series_code} ${s.series_name} ${s.short_name} ${s.description} ${s.subcategory} ${s.category}`
      );
      let score = 0;
      let reason = "";
      if (hay.includes(q)) {
        score += 100;
        reason = `Coincidencia directa con "${sp.get("q")}"`;
      }
      for (const tok of tokens) {
        if (hay.includes(tok)) {
          score += 30;
          if (!reason) reason = `Contiene término "${tok}"`;
        }
      }
      if (score > 0) {
        results.push({
          series_code: s.series_code,
          series_name: s.series_name,
          short_name: s.short_name,
          description: s.description,
          category: s.category,
          subcategory: s.subcategory,
          is_context_variable: s.is_context_variable,
          source_institution: s.source_institution,
          unit: s.unit,
          frequency: s.frequency,
          start_date: s.start_date,
          last_observation_date: s.last_observation_date,
          audit_status: s.audit_status,
          series_type: s.series_type,
          quality_score: s.quality_score,
          match_reason: reason,
          score,
        });
      }
    }
    results.sort((a, b) => b.score - a.score);
    return { query: sp.get("q") || "", count: results.length, results } as T;
  }

  if (pathname === "/api/compare") {
    const codes = (sp.get("series") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const mode = sp.get("mode") || "base_100";
    const startDate = sp.get("start_date");
    const endDate = sp.get("end_date");
    const alignMonthly = (sp.get("align_monthly") as "avg" | "eop") || "avg";

    const selected = codes.map((c) => snap.series_detail[c]).filter(Boolean);
    const hasDaily = selected.some((s) => s.frequency === "DAILY");
    const hasLower = selected.some((s) => s.frequency !== "DAILY");
    const warnings: Array<{ code: string; severity: string; message: string }> = [];

    const units = new Set(selected.map((s) => s.unit));
    if (units.size > 1 && mode === "original") {
      warnings.push({
        code: "DIFFERENT_UNITS",
        severity: "warning",
        message: "Las series seleccionadas tienen distintas unidades de medida; se recomienda utilizar Base 100 o Variación interanual.",
      });
    }
    if (hasDaily && hasLower) {
      warnings.push({
        code: "DIFFERENT_FREQUENCIES",
        severity: "info",
        message: `Las series diarias fueron agregadas a frecuencia mensual (${alignMonthly === "eop" ? "fin de mes" : "promedio mensual"}).`,
      });
    }

    let commonBaseDate = sp.get("base_date");
    const preparedMap = new Map<string, { effFreq: string; pts: ObservationPoint[] }>();
    for (const s of selected) {
      let pts = snap.series_observations_raw[s.series_code]?.observations || [];
      let effFreq = s.frequency;
      if (s.frequency === "DAILY" && hasLower) {
        pts = aggregateDailyToMonthly(pts, alignMonthly);
        effFreq = "MONTHLY";
      }
      preparedMap.set(s.series_code, { effFreq, pts });
    }

    if (mode === "base_100" && !commonBaseDate) {
      const firstDates: string[] = [];
      for (const s of selected) {
        const pts = preparedMap.get(s.series_code)?.pts || [];
        const cand = pts.find((p) => !startDate || p.date >= startDate);
        if (cand) firstDates.push(cand.date);
      }
      if (firstDates.length > 0) {
        commonBaseDate = firstDates.sort().slice(-1)[0];
      }
    }

    const seriesOut = selected.map((s) => {
      const prep = preparedMap.get(s.series_code)!;
      const tMode = mode === "original" ? "level" : mode;
      const { rows } = transformPoints(prep.pts, prep.effFreq, tMode, commonBaseDate);
      const filtered = rows.filter(
        (r) => (!startDate || r.date >= startDate) && (!endDate || r.date <= endDate)
      );
      return {
        series_code: s.series_code,
        series_name: s.series_name,
        short_name: s.short_name,
        unit: s.unit,
        frequency: s.frequency,
        effective_frequency: prep.effFreq,
        series_type: s.series_type,
        is_context_variable: s.is_context_variable,
        seasonal_adjustment: s.seasonal_adjustment,
        price_type: s.price_type,
        source_institution: s.source_institution,
        observations: filtered,
      };
    });

    const resp: CompareResponse = {
      mode,
      base_date: commonBaseDate || null,
      align_monthly: hasDaily && hasLower ? alignMonthly : null,
      warnings,
      correlation_caution:
        "Advertencia metodológica: la coincidencia visual o correlación estadística entre estas series no implica causalidad. Utilice esta visualización para formular hipótesis exploratorias y contrastarlas económicamente.",
      series: seriesOut,
    };
    return resp as T;
  }

  if (pathname === "/api/research/suggest") {
    const q = normalizeText(sp.get("q") || "");
    let presetId = "local_vs_imports";
    let topic = "Relación entre importaciones textiles y producción local";
    let primaryCode = "IPI_TEXTILES";
    let relatedCodes = ["IMPO_CADENA_TEXTIL_TOTAL", "IMPO_PRENDAS_TERMINADAS_TOTAL", "TC_MAYORISTA_BCRA"];
    let hypotheses = [
      "¿Aumentaron más las importaciones de insumos intermedios (filamentos NCM 54 / tejidos NCM 60) o las de prendas terminadas (NCM 61+62)?",
      "¿El desempeño de la producción textil acompañó el ciclo de la industria manufacturera general o mostró divergencias específicas?",
      "¿Cómo se comportaron el tipo de cambio mayorista y las importaciones frente a la utilización de capacidad instalada textil?",
    ];

    if (q.includes("pyme") || q.includes("grande")) {
      presetId = "pyme_vs_large";
      topic = "Estructura empresarial: PyMEs vs grandes empresas en la cadena textil";
      primaryCode = "EMPLEO_PRIVADO_TEXTIL";
      relatedCodes = ["EMPLEO_PRIVADO_INDUMENTARIA", "UCII_TEXTILES", "PRESTAMOS_SECTOR_PRIVADO"];
      hypotheses = [
        "¿Cómo se distribuyen las firmas PyME (Micro, Pequeña, Mediana) frente a grandes empresas a lo largo de los distintos eslabones de la cadena textil?",
        "¿Qué divergencias se observan entre empleo registrado en productos textiles (CLAE 13) y confección de prendas (CLAE 14)?",
      ];
    } else if (q.includes("nacional") || q.includes("extranjera")) {
      presetId = "national_vs_foreign";
      topic = "Estructura empresarial: firmas nacionales vs extranjeras";
      primaryCode = "IPI_TEXTILES";
      relatedCodes = ["IMPO_PRENDAS_TERMINADAS_TOTAL", "EXPO_CADENA_TEXTIL_TOTAL", "TC_MAYORISTA_BCRA"];
      hypotheses = [
        "¿Se observan distintos modelos productivos (local, mixto o importador) dentro de las firmas de capital nacional frente a las de capital extranjero?",
        "¿Por qué es metodológicamente necesario separar origen societario de tamaño empresarial y de modelo productivo?",
      ];
    } else if (q.includes("terminado") || q.includes("precio") || q.includes("ropa")) {
      presetId = "local_vs_imported_finished";
      topic = "Producción local vs producto terminado importado y precios relativos";
      primaryCode = "IPI_PRENDAS_VESTIR";
      relatedCodes = ["IMPO_PRENDAS_TERMINADAS_TOTAL", "IPC_PRENDAS_CALZADO", "PRECIO_RELATIVO_INDUMENTARIA"];
      hypotheses = [
        "¿Cómo evolucionó la producción local de prendas de vestir (IPI) en relación con las importaciones de prendas terminadas (NCM 61+62)?",
        "¿Coincidieron cambios en importaciones de indumentaria terminada con movimientos en el precio relativo de la ropa (sin atribuir causalidad automática)?",
      ];
    } else if (q.includes("dependencia") || q.includes("segmento") || q.includes("insumo")) {
      presetId = "import_dependency_by_segment";
      topic = "Dependencia importadora por segmento de la cadena textil";
      primaryCode = "IMPO_NCM_54_FILAMENTOS_SINT";
      relatedCodes = ["IMPO_NCM_60_TEJIDOS_PUNTO", "IMPO_PRENDAS_TERMINADAS_TOTAL", "IPI_TEJIDOS_ACABADO"];
      hypotheses = [
        "¿Cuál es el peso relativo de las importaciones de insumos intermedios (NCM 54 filamentos, NCM 60 tejidos de punto) frente a prendas terminadas (NCM 61+62)?",
        "¿Qué eslabones de la cadena muestran mayor presencia verificada de producción local con insumos importados?",
      ];
    }

    const pSer = snap.series_detail[primaryCode];
    const rSers = relatedCodes.map((c) => snap.series_detail[c]).filter(Boolean);
    const sug: ResearchSuggestion = {
      question: sp.get("q") || "",
      suggested_topic: topic,
      framing_label: "Posible estructura exploratoria de investigación",
      methodological_caution:
        "Datos de Industria Textil Argentina (DITA) no define automáticamente qué variable es 'dependiente' ni 'explicativa' como hecho estadístico. No interpretar asociaciones entre variables agregadas ni entre dimensiones empresariales como causalidad.",
      primary_variable: pSer || null,
      related_variables: rSers,
      exploratory_questions: hypotheses,
      structural_preset_id: presetId,
    };
    return sug as T;
  }

  if (pathname === "/api/trade/chain") return snap.trade_chain as T;
  if (pathname === "/api/glossary") return snap.glossary as T;
  if (pathname === "/api/sources") return snap.sources as T;
  if (pathname === "/api/updates") return snap.updates as T;
  if (pathname === "/api/auditor/summary") return snap.auditor_summary as T;
  if (pathname === "/api/auditor/series") return snap.auditor_series as T;

  // Industry Structure endpoints
  if (pathname === "/api/industry-structure/taxonomy") return snap.industry_taxonomy as T;

  const companies = getStoredCompanies(snap);

  if (pathname === "/api/industry-structure/summary") {
    return recomputeSummary(snap.industry_summary, companies) as T;
  }

  if (pathname === "/api/industry-structure/companies" && method === "GET") {
    const splitParam = (k: string) =>
      sp
        .getAll(k)
        .flatMap((v) => v.split(","))
        .map((s) => s.trim())
        .filter(Boolean);
    const sizes = splitParam("size");
    const origins = splitParam("origin");
    const models = splitParam("production_model");
    const chains = splitParam("chain_position");
    const chainMatch = sp.get("chain_match") || "any";
    const q = sp.get("q");
    const filtered = filterCompaniesList(companies, {
      sizes,
      origins,
      models,
      chains,
      chainMatch,
      q,
    });
    const resp: CompaniesListResponse = {
      count: filtered.length,
      filters_applied: {
        size: sizes,
        origin: origins,
        production_model: models,
        chain_position: chains,
        chain_match: chainMatch,
        classification_status: sp.get("classification_status"),
        q,
      },
      items: filtered,
    };
    return resp as T;
  }

  if (pathname === "/api/industry-structure/companies" && method === "POST") {
    const body = JSON.parse(String(init?.body || "{}")) as {
      legal_name: string;
      brand_name?: string | null;
      cuit?: string | null;
      notes?: string | null;
    };
    const nextId = companies.reduce((m, c) => Math.max(m, c.company_id), 0) + 1;
    const nowIso = new Date().toISOString();
    const created: CompanyDetail = {
      company_id: nextId,
      legal_name: (body.legal_name || "").trim(),
      brand_name: body.brand_name?.trim() || null,
      cuit: body.cuit?.trim() || null,
      company_size: "UNKNOWN",
      company_size_label: "No determinado",
      company_origin: "UNKNOWN",
      company_origin_label: "No determinado",
      production_model: "UNKNOWN",
      production_model_label: "No determinado",
      chain_positions: ["UNKNOWN"],
      chain_position_labels: ["No determinado"],
      classification_status: "UNKNOWN",
      classification_status_label: "No determinada (UNKNOWN)",
      notes: body.notes?.trim() || null,
      created_at: nowIso,
      updated_at: nowIso,
      classification_history: [],
    };
    const updated = [...companies, created];
    saveStoredCompanies(updated);
    return created as T;
  }

  const compDetailMatch = pathname.match(/^\/api\/industry-structure\/companies\/(\d+)$/);
  if (compDetailMatch && method === "GET") {
    const cid = Number(compDetailMatch[1]);
    const found = companies.find((c) => c.company_id === cid);
    if (!found) throw new Error(`Empresa ${cid} no encontrada.`);
    return found as T;
  }

  const compClsMatch = pathname.match(/^\/api\/industry-structure\/companies\/(\d+)\/classifications$/);
  if (compClsMatch && method === "POST") {
    const cid = Number(compClsMatch[1]);
    const foundIdx = companies.findIndex((c) => c.company_id === cid);
    if (foundIdx === -1) throw new Error(`Empresa ${cid} no encontrada.`);
    const comp = { ...companies[foundIdx], classification_history: [...(companies[foundIdx].classification_history || [])] };
    const body = JSON.parse(String(init?.body || "{}")) as {
      dimension: string;
      classification: string;
      valid_from: string;
      valid_to?: string | null;
      official_source_id?: number | null;
      source_url?: string | null;
      evidence: string;
    };

    const dim = body.dimension.toUpperCase();
    const cls = body.classification.toUpperCase();
    const dimMeta = snap.industry_taxonomy.dimensions.find((d) => d.key === dim);
    const optMeta = dimMeta?.options.find((o) => o.code === cls);
    const srcMeta = snap.industry_summary.approved_official_sources.find(
      (s) => s.official_source_id === body.official_source_id
    );

    const reasons: string[] = [];
    if (cls !== "UNKNOWN") {
      if (!srcMeta) {
        reasons.push("Falta fuente oficial aprobada en core.official_sources.");
      }
      const urlStr = (body.source_url || "").trim();
      if (!urlStr) {
        reasons.push("Falta source_url oficial verificable.");
      } else {
        try {
          const host = new URL(urlStr).hostname.toLowerCase();
          if (FORBIDDEN_DOMAINS.some((fd) => host === fd || host.endsWith(`.${fd}`))) {
            reasons.push(`Dominio prohibido por regla de fuentes (${host}).`);
          } else if (srcMeta && host !== srcMeta.official_domain && !host.endsWith(`.${srcMeta.official_domain}`)) {
            reasons.push(`El host ${host} no coincide con el dominio oficial ${srcMeta.official_domain}.`);
          }
        } catch {
          reasons.push("source_url inválida.");
        }
      }
      const ev = (body.evidence || "").trim();
      if (ev.length < 20) {
        reasons.push("Evidencia insuficiente (mínimo 20 caracteres citando documento oficial).");
      } else if (/wikipedia|instagram|facebook|tiktok|linkedin|twitter|red social|web comercial|noticia|conocimiento del modelo|percepci[oó]n/i.test(ev)) {
        reasons.push("Referencia a fuente no oficial o inferencia prohibida por regla de fuentes.");
      }
    }

    const auditStatus = reasons.length === 0 ? "VERIFIED" : "REJECTED";
    const auditNotes =
      reasons.length === 0
        ? "Evidencia oficial verificada y aprobada por CompanyClassificationAuditor."
        : reasons.join(" | ");

    const nextHistId =
      comp.classification_history.reduce((m, h) => Math.max(m, h.history_id), 0) + 1;
    const newHist: CompanyClassificationHistoryItem = {
      history_id: nextHistId,
      company_id: cid,
      dimension: dim,
      classification: cls,
      classification_label: optMeta?.label || cls,
      valid_from: body.valid_from,
      valid_to: body.valid_to || null,
      official_source_id: srcMeta?.official_source_id ?? null,
      official_source_code: srcMeta?.source_code ?? null,
      official_source_institution: srcMeta?.institution ?? null,
      source_url: body.source_url || null,
      evidence: body.evidence || "UNKNOWN",
      audit_status: auditStatus,
      audit_notes: auditNotes,
      recorded_at: new Date().toISOString(),
    };
    comp.classification_history = [newHist, ...comp.classification_history];

    if (auditStatus === "VERIFIED" && !body.valid_to) {
      if (dim === "SIZE") {
        comp.company_size = cls;
        comp.company_size_label = optMeta?.label || cls;
      } else if (dim === "ORIGIN") {
        comp.company_origin = cls;
        comp.company_origin_label = optMeta?.label || cls;
      } else if (dim === "PRODUCTION_MODEL") {
        comp.production_model = cls;
        comp.production_model_label = optMeta?.label || cls;
      } else if (dim === "CHAIN_POSITION") {
        const nextPositions =
          cls === "UNKNOWN"
            ? ["UNKNOWN"]
            : Array.from(new Set([...comp.chain_positions.filter((p) => p !== "UNKNOWN"), cls]));
        comp.chain_positions = nextPositions;
        const posDim = snap.industry_taxonomy.dimensions.find((d) => d.key === "CHAIN_POSITION");
        comp.chain_position_labels = nextPositions.map(
          (p) => posDim?.options.find((o) => o.code === p)?.label || p
        );
      }
      const verifiedDims =
        (comp.company_size !== "UNKNOWN" ? 1 : 0) +
        (comp.company_origin !== "UNKNOWN" ? 1 : 0) +
        (comp.production_model !== "UNKNOWN" ? 1 : 0) +
        (comp.chain_positions.some((p) => p !== "UNKNOWN") ? 1 : 0);
      comp.classification_status =
        verifiedDims === 4 ? "VERIFIED_COMPLETE" : verifiedDims > 0 ? "PARTIALLY_VERIFIED" : "UNKNOWN";
    }

    const nextCompanies = [...companies];
    nextCompanies[foundIdx] = comp;
    saveStoredCompanies(nextCompanies);

    return {
      audit_result: {
        history_id: nextHistId,
        dimension: dim,
        classification: cls,
        audit_status: auditStatus,
        audit_notes: auditNotes,
        promoted_to_company: auditStatus === "VERIFIED" && !body.valid_to,
      },
      company: comp,
    } as T;
  }

  if (pathname === "/api/industry-structure/research-presets") {
    return snap.industry_presets as T;
  }

  if (pathname === "/api/industry-structure/research-builder" && method === "POST") {
    const body = JSON.parse(String(init?.body || "{}")) as {
      preset_id?: string | null;
      sizes?: string[];
      origins?: string[];
      production_models?: string[];
      chain_positions?: string[];
      custom_focus?: string | null;
    };
    if (body.preset_id) {
      const p = snap.industry_presets.find((x) => x.preset_id === body.preset_id) || snap.industry_presets[0];
      const frame: StructuralResearchFrame = {
        mode: "preset",
        preset_id: p.preset_id,
        title: p.title,
        dimensions_involved: p.dimensions_involved,
        segment_comparison: {
          segment_a: {
            label: p.segment_a.label,
            filters: p.segment_a.filters,
            verified_company_count: p.segment_a_company_count,
          },
          segment_b: {
            label: p.segment_b.label,
            filters: p.segment_b.filters,
            verified_company_count: p.segment_b_company_count,
          },
          companies_with_unknown_status: companies.filter((c) => c.classification_status === "UNKNOWN").length,
        },
        exploratory_questions: p.exploratory_questions,
        recommended_series: p.recommended_series_details,
        non_causality_warning: p.non_causality_warning,
        data_coverage_note:
          "Los conteos de firmas reflejan únicamente registros cargados con evidencia oficial verificable. Las dimensiones sin respaldo documental oficial se mantienen explícitamente en UNKNOWN.",
      };
      return frame as T;
    }

    const matched = filterCompaniesList(companies, {
      sizes: body.sizes,
      origins: body.origins,
      models: body.production_models,
      chains: body.chain_positions,
    });
    const recSeries = snap.industry_presets[0]?.recommended_series_details || [];
    const descParts = [
      ...(body.sizes?.length ? [`Tamaño: ${body.sizes.join(", ")}`] : []),
      ...(body.origins?.length ? [`Origen: ${body.origins.join(", ")}`] : []),
      ...(body.production_models?.length ? [`Modelo: ${body.production_models.join(", ")}`] : []),
      ...(body.chain_positions?.length ? [`Cadena: ${body.chain_positions.join(", ")}`] : []),
    ];
    const desc = descParts.length ? descParts.join(" + ") : "Universo completo";
    const frame: StructuralResearchFrame = {
      mode: "custom",
      preset_id: null,
      title: `Exploración estructural: ${desc}`,
      dimensions_involved: ["SIZE", "ORIGIN", "PRODUCTION_MODEL", "CHAIN_POSITION"],
      segment_profile: {
        description: desc,
        filters: {
          sizes: body.sizes || [],
          origins: body.origins || [],
          production_models: body.production_models || [],
          chain_positions: body.chain_positions || [],
        },
        matching_companies_count: matched.length,
        total_registered_companies: companies.length,
      },
      exploratory_questions: [
        `¿Qué evolución muestran las series sectoriales oficiales en los eslabones vinculados al segmento [${desc}]?`,
        `¿Cómo se distribuyen las demás dimensiones independientes dentro del subconjunto [${desc}] sin asumir homogeneidad interna?`,
        "¿Qué proporción de firmas relevantes en este segmento cuenta con evidencia oficial verificable frente a registros aún clasificados como UNKNOWN?",
      ],
      recommended_series: recSeries,
      non_causality_warning:
        "Advertencia metodológica estricta: no interpretar asociaciones entre la estructura empresarial y la evolución de series económicas agregadas como relaciones de causalidad.",
      data_coverage_note:
        "Las cuatro dimensiones (Tamaño, Origen, Modelo productivo y Posición en la cadena) se mantienen independientes.",
    };
    return frame as T;
  }

  throw new Error(`Ruta no soportada en modo standalone: ${pathname}`);
}
