"use client";

import React, { useState, useMemo } from "react";
import {
  ProjectCorrelationReport,
  CorrelationDimension,
  CorrelationDataPoint,
  UnifiedScopeMetrics,
} from "@/types/analysis";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Network,
  Activity,
  Layers,
  Calculator,
  GitBranch,
  Info,
  AlertTriangle,
  Scale,
  ShieldCheck,
} from "lucide-react";

interface ProjectCorrelationSectionProps {
  correlation: ProjectCorrelationReport | null | undefined;
  scopes?: UnifiedScopeMetrics[] | null | undefined;
}

interface DimensionMeta {
  label: string;
  shortLabel?: string;
  yAxisLabel: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const DIMENSION_METADATA: Record<string, DimensionMeta> = {
  cyclomatic_vs_statement_count: {
    label: "Cyclomatic vs Statement Count",
    shortLabel: "Statement Count",
    yAxisLabel: "Statement Count",
    description: "Evaluates co-variation between decision points and total statement count.",
    icon: Layers,
  },
  cyclomatic_vs_ast_depth: {
    label: "Cyclomatic vs AST Depth",
    shortLabel: "AST Depth",
    yAxisLabel: "Max AST Depth",
    description: "Evaluates co-variation between branching logic and syntax tree nesting depth.",
    icon: GitBranch,
  },
  cyclomatic_vs_control_nesting_depth: {
    label: "Cyclomatic vs Nesting Depth",
    shortLabel: "Nesting Depth",
    yAxisLabel: "Control Nesting Depth",
    description: "Evaluates relationship between decision complexity and control block nesting levels.",
    icon: Activity,
  },
  cyclomatic_vs_halstead_volume: {
    label: "Cyclomatic vs Halstead Volume",
    shortLabel: "Halstead Volume",
    yAxisLabel: "Halstead Volume (bits)",
    description: "Compares graph decision points against Halstead information-theoretic code volume.",
    icon: Calculator,
  },
  cyclomatic_vs_halstead_effort: {
    label: "Cyclomatic vs Halstead Effort",
    shortLabel: "Halstead Effort",
    yAxisLabel: "Halstead Effort (E)",
    description: "Compares decision structure against Halstead mental effort score.",
    icon: Scale,
  },
};

function formatCoeff(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  if (!Number.isFinite(val)) return "—";
  return val.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatInt(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  if (!Number.isFinite(val)) return "—";
  return val.toLocaleString("en-US");
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{ payload: CorrelationDataPoint }>;
  scopeMap: Map<string, UnifiedScopeMetrics>;
  yLabel: string;
}

const CustomScatterTooltip: React.FC<CustomTooltipProps> = ({
  active,
  payload,
  scopeMap,
  yLabel,
}) => {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  const matchedScope = scopeMap.get(point.scope_id);

  const lineSpan =
    matchedScope?.lineno != null
      ? matchedScope.end_lineno != null && matchedScope.end_lineno !== matchedScope.lineno
        ? `L${matchedScope.lineno}–L${matchedScope.end_lineno}`
        : `L${matchedScope.lineno}`
      : null;

  return (
    <div className="p-2.5 rounded-lg bg-zinc-900/95 border border-zinc-700 shadow-xl text-xs space-y-1.5 font-mono max-w-xs">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-800 pb-1">
        <span className="font-bold text-zinc-100 font-sans truncate">
          {matchedScope?.name || point.scope_id}
        </span>
        {matchedScope?.scope_type && (
          <span className="px-1.5 py-0.2 rounded text-[9px] bg-zinc-800 text-zinc-300 border border-zinc-700 uppercase font-sans">
            {matchedScope.scope_type === "class_body" ? "class" : matchedScope.scope_type}
          </span>
        )}
      </div>

      <div className="text-[10px] text-zinc-500 font-mono truncate" title={point.scope_id}>
        id: {point.scope_id}
      </div>

      {lineSpan && (
        <div className="text-[10px] text-zinc-400">
          Source location: <span className="text-zinc-200">{lineSpan}</span>
        </div>
      )}

      <div className="pt-1 border-t border-zinc-800/80 space-y-0.5 text-[11px]">
        <div className="flex justify-between gap-3">
          <span className="text-zinc-400">Cyclomatic (M):</span>
          <span className="font-bold text-emerald-400">{point.cyclomatic_complexity}</span>
        </div>
        <div className="flex justify-between gap-3">
          <span className="text-zinc-400">{yLabel}:</span>
          <span className="font-bold text-cyan-400">
            {Number.isInteger(point.metric_value)
              ? formatInt(point.metric_value)
              : formatCoeff(point.metric_value)}
          </span>
        </div>
      </div>
    </div>
  );
};

export const ProjectCorrelationSection: React.FC<ProjectCorrelationSectionProps> = ({
  correlation,
  scopes,
}) => {
  const dimensionsMap = correlation?.dimensions;
  const dimensionKeys = useMemo(() => {
    return dimensionsMap ? Object.keys(dimensionsMap) : [];
  }, [dimensionsMap]);

  const [selectedDimensionKey, setSelectedDimensionKey] = useState<string | null>(null);

  // Re-resolve active dimension selection safely if dimension list changes
  const activeDimensionKey = useMemo(() => {
    if (dimensionKeys.length === 0) return null;
    if (selectedDimensionKey && dimensionKeys.includes(selectedDimensionKey)) {
      return selectedDimensionKey;
    }
    return dimensionKeys[0];
  }, [dimensionKeys, selectedDimensionKey]);

  const activeDimension: CorrelationDimension | null = useMemo(() => {
    if (!dimensionsMap || !activeDimensionKey) return null;
    return dimensionsMap[activeDimensionKey] ?? null;
  }, [dimensionsMap, activeDimensionKey]);

  // Fast scope lookup map for tooltip metadata enrichment
  const scopeMap = useMemo(() => {
    const map = new Map<string, UnifiedScopeMetrics>();
    if (scopes) {
      for (const s of scopes) {
        map.set(s.scope_id, s);
      }
    }
    return map;
  }, [scopes]);

  // Validate chart data points (guarantee finite coordinates)
  const chartPoints = useMemo(() => {
    if (!activeDimension?.pairs) return [];
    return activeDimension.pairs.filter(
      (p) =>
        Number.isFinite(p.cyclomatic_complexity) &&
        Number.isFinite(p.metric_value)
    );
  }, [activeDimension]);

  // Missing data or unavailable correlation state
  if (!correlation) {
    return (
      <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl text-center">
        <p className="text-xs text-zinc-500 font-mono">
          Project correlation analysis is unavailable for this analysis run.
        </p>
      </div>
    );
  }

  if (dimensionKeys.length === 0) {
    return (
      <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl text-center">
        <p className="text-xs text-zinc-500 font-mono">
          No correlation dimensions were returned for this submission.
        </p>
      </div>
    );
  }

  const activeMeta = activeDimensionKey
    ? DIMENSION_METADATA[activeDimensionKey] || {
        label: activeDimensionKey.replace(/_/g, " "),
        yAxisLabel: "Metric Value",
        description: "Correlation between cyclomatic complexity and metric dimension.",
        icon: Network,
      }
    : null;

  const getStatusBadge = (status: CorrelationDimension["status"]) => {
    switch (status) {
      case "DESCRIPTIVE_ONLY":
        return (
          <span className="px-1.5 py-0.2 rounded text-[9px] font-sans font-medium uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Descriptive
          </span>
        );
      case "INSUFFICIENT_SAMPLE":
        return (
          <span className="px-1.5 py-0.2 rounded text-[9px] font-sans font-medium uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Sample n &lt; 3
          </span>
        );
      case "ZERO_VARIANCE":
        return (
          <span className="px-1.5 py-0.2 rounded text-[9px] font-sans font-medium uppercase tracking-wider bg-purple-500/10 text-purple-400 border border-purple-500/20">
            Zero Variance
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div
      role="region"
      aria-label="Project Metric Correlations"
      className="space-y-3"
    >
      {/* 1. Header & Overview Strip */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100 tracking-tight">
              Project Metric Correlations
            </h3>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Phase 1B.2
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-0.5">
            Statistical co-variation between cyclomatic complexity and structural/Halstead dimensions across complete procedural scopes.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-zinc-400 shrink-0">
          <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800">
            Eligible scopes:{" "}
            <strong className="text-zinc-200">
              {formatInt(correlation.eligible_scope_count)}
            </strong>
          </span>
          <span className="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800">
            Dimensions:{" "}
            <strong className="text-zinc-200">{dimensionKeys.length}</strong>
          </span>
        </div>
      </div>

      {/* 2. Dimension Comparison Cards Grid */}
      <div
        role="tablist"
        aria-label="Correlation Dimensions"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5"
      >
        {dimensionKeys.map((key) => {
          const dim = dimensionsMap![key];
          const isSelected = key === activeDimensionKey;
          const meta = DIMENSION_METADATA[key] || {
            label: key.replace(/_/g, " "),
            yAxisLabel: "Metric Value",
            description: "",
            icon: Network,
          };
          const IconComponent = meta.icon;

          return (
            <button
              key={key}
              role="tab"
              aria-selected={isSelected}
              tabIndex={0}
              onClick={() => setSelectedDimensionKey(key)}
              className={`p-3 rounded-xl border text-left transition-all duration-150 flex flex-col justify-between focus:outline-hidden focus:ring-1 focus:ring-emerald-500/50 cursor-pointer ${
                isSelected
                  ? "bg-zinc-800 border-emerald-500/50 shadow-md shadow-emerald-500/5"
                  : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700/80 hover:bg-zinc-900/90"
              }`}
            >
              <div>
                <div className="flex items-center justify-between text-zinc-400 mb-1.5">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400 truncate">
                    {meta.shortLabel || meta.label}
                  </span>
                  <IconComponent
                    className={`w-3.5 h-3.5 shrink-0 ${
                      isSelected ? "text-emerald-400" : "text-zinc-500"
                    }`}
                  />
                </div>

                <div className="flex items-baseline gap-2 mt-0.5">
                  <div className="flex flex-col">
                    <span className="text-[9px] uppercase tracking-wider text-zinc-500">
                      Pearson r
                    </span>
                    <span
                      className={`text-lg font-bold font-mono ${
                        dim.pearson_r != null
                          ? "text-emerald-400"
                          : "text-zinc-500"
                      }`}
                    >
                      {formatCoeff(dim.pearson_r)}
                    </span>
                  </div>

                  <div className="flex flex-col ml-auto text-right">
                    <span className="text-[9px] uppercase tracking-wider text-zinc-500">
                      Spearman ρ
                    </span>
                    <span
                      className={`text-lg font-bold font-mono ${
                        dim.spearman_rho != null
                          ? "text-cyan-400"
                          : "text-zinc-500"
                      }`}
                    >
                      {formatCoeff(dim.spearman_rho)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex items-center justify-between text-[10px] font-mono">
                <span className="text-zinc-500">n = {dim.sample_size}</span>
                {getStatusBadge(dim.status)}
              </div>
            </button>
          );
        })}
      </div>

      {/* 3. Detailed Dimension Inspection & Scatter Plot Area */}
      {activeDimension && activeMeta && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden shadow-xs">
          {/* Active Dimension Header */}
          <div className="p-4 bg-zinc-900/90 border-b border-zinc-800 flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-zinc-100 font-sans tracking-tight">
                  {activeMeta.label}
                </h4>
                {getStatusBadge(activeDimension.status)}
              </div>
              <p className="text-xs text-zinc-400">
                {activeMeta.description}
              </p>
            </div>

            {/* Dimension KPI Badges */}
            <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
              <div className="px-2.5 py-1 rounded bg-zinc-950/70 border border-zinc-800">
                <span className="text-zinc-500 mr-1.5">Pearson (r):</span>
                <span className="font-bold text-emerald-400">
                  {formatCoeff(activeDimension.pearson_r)}
                </span>
              </div>
              <div className="px-2.5 py-1 rounded bg-zinc-950/70 border border-zinc-800">
                <span className="text-zinc-500 mr-1.5">Spearman (ρ):</span>
                <span className="font-bold text-cyan-400">
                  {formatCoeff(activeDimension.spearman_rho)}
                </span>
              </div>
              <div className="px-2.5 py-1 rounded bg-zinc-950/70 border border-zinc-800">
                <span className="text-zinc-500 mr-1.5">Sample Size:</span>
                <span className="font-bold text-zinc-200">
                  {activeDimension.sample_size} scopes
                </span>
              </div>
            </div>
          </div>

          {/* Diagnostic Banner if present */}
          {activeDimension.diagnostic_message && (
            <div className="px-4 py-2.5 bg-amber-500/10 border-b border-amber-500/20 text-xs text-amber-300 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>
                <strong>Diagnostic notice:</strong>{" "}
                {activeDimension.diagnostic_message}
              </span>
            </div>
          )}

          {/* Scatter Plot Body */}
          <div className="p-4">
            {chartPoints.length > 0 ? (
              <div className="w-full">
                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart
                      margin={{ top: 15, right: 25, bottom: 25, left: 10 }}
                    >
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="#27272a"
                      />
                      <XAxis
                        type="number"
                        dataKey="cyclomatic_complexity"
                        name="Cyclomatic Complexity"
                        stroke="#71717a"
                        tick={{ fill: "#a1a1aa", fontSize: 11 }}
                        domain={["auto", "auto"]}
                        label={{
                          value: "Cyclomatic Complexity (M)",
                          position: "insideBottom",
                          offset: -12,
                          fill: "#71717a",
                          fontSize: 11,
                        }}
                      />
                      <YAxis
                        type="number"
                        dataKey="metric_value"
                        name={activeMeta.yAxisLabel}
                        stroke="#71717a"
                        tick={{ fill: "#a1a1aa", fontSize: 11 }}
                        domain={["auto", "auto"]}
                        label={{
                          value: activeMeta.yAxisLabel,
                          angle: -90,
                          position: "insideLeft",
                          offset: 5,
                          fill: "#71717a",
                          fontSize: 11,
                        }}
                      />
                      <Tooltip
                        cursor={{ strokeDasharray: "3 3", stroke: "#52525b" }}
                        content={
                          <CustomScatterTooltip
                            scopeMap={scopeMap}
                            yLabel={activeMeta.yAxisLabel}
                          />
                        }
                      />
                      <Scatter
                        name={activeMeta.label}
                        data={chartPoints}
                        fill="#10b981"
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>

                <div className="mt-2 flex flex-col sm:flex-row sm:items-center justify-between text-[11px] font-mono text-zinc-500 pt-2 border-t border-zinc-800/60 gap-1">
                  <span>
                    Plotting {chartPoints.length} observation{" "}
                    {chartPoints.length === 1 ? "pair" : "pairs"} (Backend sample
                    size: {activeDimension.sample_size})
                  </span>
                  <span>Hover points for function &amp; line metadata</span>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center space-y-1 text-zinc-500">
                <Info className="w-5 h-5 mx-auto text-zinc-600 mb-1" />
                <p className="text-xs font-mono">
                  No observation pairs available for {activeMeta.label}.
                </p>
                <p className="text-[11px] text-zinc-600">
                  {activeDimension.diagnostic_message ||
                    "Submit Python functions or methods with complete CFG analysis to generate data points."}
                </p>
              </div>
            )}
          </div>

          {/* 4. Statistical Disclaimer Footer */}
          <div className="p-3 bg-zinc-950/60 border-t border-zinc-800 flex items-start gap-2 text-[11px] text-zinc-400">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div className="space-y-0.5">
              <p className="text-zinc-300 font-medium font-sans">
                Statistical Interpretation Guidance
              </p>
              <p className="text-zinc-400 font-sans text-[11px] leading-relaxed">
                {correlation.disclaimer}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
