import seriesCodes from "@/data/series_codes.json";
import { IndicadorDetailClient } from "./IndicadorDetailClient";

export function generateStaticParams() {
  return seriesCodes.map((code) => ({ series_code: code }));
}

export default async function IndicadorDetailPage({
  params,
}: {
  params: Promise<{ series_code: string }>;
}) {
  const { series_code } = await params;
  return <IndicadorDetailClient initialCode={series_code} />;
}
