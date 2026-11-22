import { standaloneApiFetch } from "./standalone-engine";

const API_BASE =
  typeof window === "undefined"
    ? process.env.BACKEND_URL || "http://127.0.0.1:8000"
    : "";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
    });
    const contentType = res.headers.get("content-type") || "";
    if (!res.ok || !contentType.includes("application/json")) {
      throw new Error(`HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } catch {
    if (typeof window !== "undefined") {
      return standaloneApiFetch<T>(path, init);
    }
    throw new Error("API backend unavailable during SSR");
  }
}

export function formatNumber(val: number | null | undefined, decimals = 2): string {
  if (val === null || val === undefined || Number.isNaN(val)) return "Datos no disponibles";
  return new Intl.NumberFormat("es-AR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

export function formatDateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  const parts = iso.slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

export function formatMonthYear(iso: string | null | undefined): string {
  if (!iso) return "—";
  const months = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const parts = iso.slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const m = parseInt(parts[1], 10);
  if (Number.isNaN(m) || m < 1 || m > 12) return iso;
  return `${months[m - 1]} ${parts[0]}`;
}

export function frequencyLabel(freq: string): string {
  switch (freq) {
    case "DAILY":
      return "Diaria";
    case "MONTHLY":
      return "Mensual";
    case "QUARTERLY":
      return "Trimestral";
    default:
      return freq;
  }
}

export function categoryLabel(cat: string): string {
  switch (cat) {
    case "actividad_produccion":
      return "Actividad y producción";
    case "precios_costes":
      return "Precios y costes";
    case "comercio_exterior":
      return "Comercio exterior";
    case "empleo_salarios":
      return "Empleo y salarios";
    case "contexto_macro":
      return "Contexto macroeconómico";
    default:
      return cat;
  }
}
