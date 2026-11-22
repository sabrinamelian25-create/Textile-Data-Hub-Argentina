import type { Metadata } from "next";
import "./globals.css";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { GlossaryProvider } from "@/components/GlossaryTooltip";

export const metadata: Metadata = {
  title: "Datos de Industria Textil Argentina (DITA) — Datos económicos sectoriales oficiales",
  description:
    "Plataforma académica de datos oficiales verificados sobre industria textil, indumentaria, comercio exterior NCM, empleo SIPA, precios y contexto macroeconómico de Argentina.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className="flex min-h-screen flex-col bg-canvas font-sans text-ink antialiased">
        <GlossaryProvider>
          <Navbar />
          <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 lg:px-8">{children}</main>
          <Footer />
        </GlossaryProvider>
      </body>
    </html>
  );
}
