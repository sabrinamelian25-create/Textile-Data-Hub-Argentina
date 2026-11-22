"use client";

import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";
import { Download, RotateCcw } from "lucide-react";

export interface ChartSeriesInput {
  name: string;
  unit: string;
  color?: string;
  data: Array<{ date: string; value: number; is_preliminary?: boolean; is_outlier_flagged?: boolean }>;
}

const PALETTE = ["#1E3A5F", "#0F766E", "#B45309", "#6D28D9"];

export function TimeSeriesChart({
  series,
  height = 390,
  title,
  yAxisName,
  dualAxis = false,
}: {
  series: ChartSeriesInput[];
  height?: number;
  title?: string;
  yAxisName?: string;
  dualAxis?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;

    const ro = new ResizeObserver(() => {
      chart.resize();
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const useDual = dualAxis && series.length === 2 && series[0].unit !== series[1].unit;
    const allDates = Array.from(
      new Set(series.flatMap((s) => s.data.map((d) => d.date)))
    ).sort();

    const yAxes: echarts.YAXisComponentOption[] = useDual
      ? [
          {
            type: "value",
            name: series[0].unit,
            nameTextStyle: { color: PALETTE[0], fontSize: 11 },
            axisLabel: { color: "#4B5563", fontSize: 11 },
            splitLine: { lineStyle: { color: "#F1F5F9" } },
          },
          {
            type: "value",
            name: series[1].unit,
            nameTextStyle: { color: PALETTE[1], fontSize: 11 },
            axisLabel: { color: "#4B5563", fontSize: 11 },
            splitLine: { show: false },
          },
        ]
      : [
          {
            type: "value",
            name: yAxisName || series[0]?.unit || "",
            nameTextStyle: { color: "#4B5563", fontSize: 11 },
            axisLabel: { color: "#4B5563", fontSize: 11 },
            splitLine: { lineStyle: { color: "#F1F5F9" } },
          },
        ];

    const option: echarts.EChartsOption = {
      animationDuration: 280,
      backgroundColor: "#FFFFFF",
      color: PALETTE,
      tooltip: {
        trigger: "axis",
        backgroundColor: "#FFFFFF",
        borderColor: "#E5E7EB",
        textStyle: { color: "#111827", fontSize: 12 },
        axisPointer: { type: "cross", label: { backgroundColor: "#1E3A5F" } },
        valueFormatter: (value) =>
          typeof value === "number"
            ? new Intl.NumberFormat("es-AR", { maximumFractionDigits: 2 }).format(value)
            : String(value ?? "Sin dato"),
      },
      legend:
        series.length > 1
          ? {
              top: 4,
              left: 8,
              icon: "roundRect",
              textStyle: { color: "#374151", fontSize: 12 },
            }
          : undefined,
      grid: {
        left: 60,
        right: useDual ? 65 : 24,
        top: series.length > 1 ? 46 : 36,
        bottom: 58,
      },
      xAxis: {
        type: "category",
        data: allDates,
        boundaryGap: false,
        axisLine: { lineStyle: { color: "#CBD5E1" } },
        axisLabel: { color: "#4B5563", fontSize: 11 },
      },
      yAxis: yAxes,
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        {
          type: "slider",
          xAxisIndex: 0,
          height: 20,
          bottom: 10,
          borderColor: "#E2E8F0",
          fillerColor: "rgba(30, 58, 95, 0.08)",
        },
      ],
      series: series.map((s, idx) => {
        const valMap = new Map(s.data.map((d) => [d.date, d]));
        return {
          name: s.name,
          type: "line",
          yAxisIndex: useDual ? idx : 0,
          showSymbol: s.data.length <= 36,
          symbolSize: 5,
          connectNulls: false, // Never silently interpolate gaps!
          lineStyle: { width: 2.2, color: s.color || PALETTE[idx % PALETTE.length] },
          itemStyle: { color: s.color || PALETTE[idx % PALETTE.length] },
          data: allDates.map((dt) => {
            const item = valMap.get(dt);
            return item ? item.value : null;
          }),
        };
      }),
    };

    chart.setOption(option, true);
  }, [series, dualAxis, yAxisName]);

  const handleResetZoom = () => {
    chartRef.current?.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
  };

  const handleDownloadPng = () => {
    if (!chartRef.current) return;
    const url = chartRef.current.getDataURL({ type: "png", pixelRatio: 2, backgroundColor: "#FFFFFF" });
    const a = document.createElement("a");
    a.href = url;
    a.download = `${(title || "grafico_textile_data_hub").toLowerCase().replace(/\s+/g, "_")}.png`;
    a.click();
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        {title ? <p className="text-xs font-medium text-slate-600">{title}</p> : <span />}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleResetZoom}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            <RotateCcw className="h-3 w-3" />
            Reajustar vista
          </button>
          <button
            type="button"
            onClick={handleDownloadPng}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
          >
            <Download className="h-3 w-3" />
            PNG
          </button>
        </div>
      </div>
      <div ref={containerRef} style={{ height: `${height}px`, width: "100%" }} />
    </div>
  );
}
