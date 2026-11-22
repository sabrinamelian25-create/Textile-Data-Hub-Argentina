"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { BarChart3, Building2, FlaskConical, Layers, Search, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { CategorySummary } from "@/lib/types";
import { SearchBar } from "@/components/SearchBar";

const DEFAULT_CATEGORIES: CategorySummary[] = [
  { code: "actividad_produccion", name: "Actividad y producción", short_description: "Producción industrial textil y de indumentaria, capacidad instalada y actividad manufacturera.", order: 1, verified_series_count: 9 },
  { code: "precios_costes", name: "Precios y costes", short_description: "IPC prendas de vestir, IPIM textil y manufacturero, energía y precios relativos.", order: 2, verified_series_count: 7 },
  { code: "comercio_exterior", name: "Comercio exterior", short_description: "Importaciones CIF y exportaciones FOB según capítulos NCM 50–63 y saldo comercial.", order: 3, verified_series_count: 14 },
  { code: "empleo_salarios", name: "Empleo y salarios", short_description: "Puestos asalariados SIPA/CLAE, remuneraciones sectoriales, RIPTE nominal y salario real.", order: 4, verified_series_count: 11 },
  { code: "contexto_macro", name: "Contexto macroeconómico", short_description: "Variables macroeconómicas de referencia (IPC, EMAE, PIB, tipo de cambio, tasas, crédito).", order: 5, verified_series_count: 8 },
];

export default function HomePage() {
  const [categories, setCategories] = useState<CategorySummary[]>(DEFAULT_CATEGORIES);

  useEffect(() => {
    apiFetch<CategorySummary[]>("/api/categories")
      .then((cats) => {
        if (Array.isArray(cats) && cats.length > 0) setCategories(cats);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="space-y-12">
      {/* Hero & Buscador Inteligente */}
      <section className="mx-auto max-w-4xl pt-4 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-800">
          <ShieldCheck className="h-3.5 w-3.5" />
          Datos oficiales auditados · INDEC · BCRA · Sec. Trabajo · CEP XXI
        </div>
        <h1 className="mt-4 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
          Textile Data Hub Argentina
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-base leading-relaxed text-slate-600">
          Infraestructura académica para investigar la industria textil e indumentaria argentina:
          series verificadas, trazabilidad completa, comparaciones metodológicas y datos listos para Excel, Python, R o Stata.
        </p>

        <div className="mt-8 text-left">
          <SearchBar />
        </div>
      </section>

      {/* Tres acciones principales */}
      <section aria-label="Acciones principales" className="grid gap-4 md:grid-cols-3">
        <Link
          href="/explorar"
          className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 transition hover:border-navy/50 hover:shadow-sm"
        >
          <div>
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-navy">
              <Search className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-slate-900">Buscar un indicador</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
              Explora series oficiales verificadas con explicaciones académicas sobre qué miden, cómo se construyen y sus limitaciones.
            </p>
          </div>
          <span className="mt-4 text-sm font-medium text-navy">Ir al catálogo sectorial →</span>
        </Link>

        <Link
          href="/comparar"
          className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-6 transition hover:border-teal/50 hover:shadow-sm"
        >
          <div>
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-teal">
              <BarChart3 className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-slate-900">Comparar variables</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
              Cruza entre 2 y 4 series en valores originales, variación interanual o Base 100 con alertas metodológicas automáticas.
            </p>
          </div>
          <span className="mt-4 text-sm font-medium text-teal">Abrir comparador →</span>
        </Link>

        <Link
          href="/research"
          className="flex flex-col justify-between rounded-xl border border-slate-200 bg-navy p-6 text-white transition hover:bg-navy/95 hover:shadow-sm"
        >
          <div>
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-white/15 text-white">
              <FlaskConical className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-semibold">Empezar un research</h2>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-200">
              Parte de tu pregunta económica, selecciona variables relacionadas, visualiza trayectorias y descarga un dataset limpio.
            </p>
          </div>
          <span className="mt-4 text-sm font-medium text-white">Iniciar recorrido guiado →</span>
        </Link>
      </section>

      {/* Cinco dimensiones sectoriales */}
      <section>
        <div className="flex items-center justify-between border-b border-slate-200 pb-3">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">Dimensiones del sector</h2>
            <p className="mt-0.5 text-sm text-slate-600">
              Organización temática de las series verificadas por Textile Data Hub
            </p>
          </div>
          <Link href="/cadena-textil" className="text-sm font-medium text-navy hover:underline">
            Ver mapa cadena NCM 50–63 →
          </Link>
        </div>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {categories.map((cat) => (
            <Link
              key={cat.code}
              href={`/explorar?category=${cat.code}`}
              className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 transition hover:border-navy/50 hover:shadow-sm"
            >
              <div>
                <div className="flex items-center justify-between">
                  <Layers className="h-4 w-4 text-navy" />
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
                    {cat.verified_series_count} series
                  </span>
                </div>
                <h3 className="mt-3 text-base font-semibold text-slate-900">{cat.name}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{cat.short_description}</p>
              </div>
              {cat.code === "contexto_macro" && (
                <span className="mt-3 inline-block rounded bg-amber-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                  Variables de contexto
                </span>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* Módulo Experimental: Estructura de la industria */}
      <section className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-800">
              <Building2 className="h-3.5 w-3.5" />
              Módulo experimental · Dimensiones independientes
            </div>
            <h2 className="text-xl font-semibold text-slate-900">Estructura de la industria</h2>
            <p className="max-w-3xl text-sm leading-relaxed text-slate-600">
              Explora la estructura empresarial del sector textil e indumentaria modelando de forma estrictamente independiente{" "}
              <strong className="font-semibold text-slate-800">Tamaño</strong>,{" "}
              <strong className="font-semibold text-slate-800">Origen</strong>,{" "}
              <strong className="font-semibold text-slate-800">Modelo productivo</strong> y{" "}
              <strong className="font-semibold text-slate-800">Posición en la cadena</strong>. Toda clasificación exige evidencia oficial verificable; ante falta de evidencia se registra <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs">UNKNOWN</code>.
            </p>
          </div>
          <Link
            href="/estructura-industria"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-navy px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-navy/90"
          >
            Abrir Estructura de la industria →
          </Link>
        </div>
      </section>
    </div>
  );
}
