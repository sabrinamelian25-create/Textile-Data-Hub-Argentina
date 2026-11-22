import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div>
          <p className="font-semibold text-slate-700">
            Datos de Industria Textil Argentina (DITA) — Laboratorio académico de investigación económica
          </p>
          <p className="mt-1">
            Exclusivamente fuentes oficiales primarias (INDEC, BCRA, Secretaría de Trabajo / SIPA, CEP XXI / Sec. de Industria y Comercio, SSPM Datos Argentina).
          </p>
        </div>
        <div className="flex flex-wrap gap-4">
          <Link href="/estructura-industria" className="hover:text-navy hover:underline">
            Estructura de la industria
          </Link>
          <Link href="/data-auditor" className="hover:text-navy hover:underline">
            Auditoría y trazabilidad
          </Link>
          <Link href="/glosario" className="hover:text-navy hover:underline">
            Glosario metodológico
          </Link>
          <Link href="/cadena-textil" className="hover:text-navy hover:underline">
            Nomenclatura NCM 50–63
          </Link>
        </div>
      </div>
    </footer>
  );
}
