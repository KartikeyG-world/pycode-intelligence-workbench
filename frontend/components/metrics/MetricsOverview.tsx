"use client";

import React from "react";
import { ProjectMetricsSummary } from "@/types/analysis";
import { Boxes, GitBranch, Layers, Calculator, Info, ShieldCheck } from "lucide-react";

interface MetricsOverviewProps {
  metrics: ProjectMetricsSummary | null | undefined;
}

function formatFloat(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined) return "—";
  if (!Number.isFinite(val)) return "—";
  return val.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatInt(val: number | null | undefined): string {
  if (val === null || val === undefined) return "—";
  return val.toLocaleString("en-US");
}

export const MetricsOverview: React.FC<MetricsOverviewProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="p-4 bg-zinc-900/40 border border-zinc-800/80 rounded-xl text-center">
        <p className="text-xs text-zinc-500 font-mono">
          Project-level metrics are unavailable for this analysis run.
        </p>
      </div>
    );
  }

  const {
    total_scopes,
    procedural_scopes,
    module_scopes,
    class_scopes,
    average_statement_count,
    average_ast_depth,
    average_control_nesting_depth,
    average_cyclomatic_complexity,
    cyclomatic_evaluated_scopes,
    average_halstead_volume,
    average_halstead_effort,
    halstead_volume_evaluated_scopes,
    halstead_effort_evaluated_scopes,
    partial_coverage_volume_scopes,
    unclassified_syntax_scopes,
  } = metrics;

  return (
    <div className="space-y-3">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100 tracking-tight">
              Project Metrics Overview
            </h3>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Static AST Metrics
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-0.5">
            Aggregated AST structural complexity, Halstead software science, and control-flow metrics across canonical scopes.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-zinc-500 shrink-0">
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-500" />
            Static Analysis
          </span>
          <span>•</span>
          <span>Zero Execution</span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Card 1: Scope Inventory */}
        <div className="p-3.5 bg-zinc-900/60 border border-zinc-800/90 rounded-xl flex flex-col justify-between hover:border-zinc-700/80 transition shadow-xs">
          <div>
            <div className="flex items-center justify-between text-zinc-400 mb-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                Scope Inventory
              </span>
              <Boxes className="w-3.5 h-3.5 text-indigo-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-zinc-100">
                {formatInt(total_scopes)}
              </span>
              <span className="text-[11px] text-zinc-500 font-sans">
                total scopes
              </span>
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-zinc-800/60 grid grid-cols-3 gap-1 text-[10px] font-mono text-zinc-400">
            <div>
              <span className="text-zinc-500 block text-[9px] uppercase">Proc</span>
              <span className="text-zinc-200 font-semibold">{procedural_scopes}</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-[9px] uppercase">Class</span>
              <span className="text-zinc-200 font-semibold">{class_scopes}</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-[9px] uppercase">Mod</span>
              <span className="text-zinc-200 font-semibold">{module_scopes}</span>
            </div>
          </div>
        </div>

        {/* Card 2: Cyclomatic Complexity */}
        <div className="p-3.5 bg-zinc-900/60 border border-zinc-800/90 rounded-xl flex flex-col justify-between hover:border-zinc-700/80 transition shadow-xs">
          <div>
            <div className="flex items-center justify-between text-zinc-400 mb-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                Avg Cyclomatic (M)
              </span>
              <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-emerald-400">
                {formatFloat(average_cyclomatic_complexity, 1)}
              </span>
              <span className="text-[11px] text-zinc-500 font-sans">
                / procedure
              </span>
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-zinc-800/60 flex items-center justify-between text-[10px] font-mono">
            <span className="text-zinc-500">Evaluated Scopes:</span>
            <span className="text-zinc-300 font-semibold">
              {cyclomatic_evaluated_scopes} of {procedural_scopes}
            </span>
          </div>
        </div>

        {/* Card 3: Structural Complexity */}
        <div className="p-3.5 bg-zinc-900/60 border border-zinc-800/90 rounded-xl flex flex-col justify-between hover:border-zinc-700/80 transition shadow-xs">
          <div>
            <div className="flex items-center justify-between text-zinc-400 mb-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                Structural Averages
              </span>
              <Layers className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-zinc-100">
                {formatFloat(average_statement_count, 1)}
              </span>
              <span className="text-[11px] text-zinc-500 font-sans">
                avg statements
              </span>
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-zinc-800/60 grid grid-cols-2 gap-2 text-[10px] font-mono">
            <div>
              <span className="text-zinc-500 block text-[9px] uppercase">AST Depth</span>
              <span className="text-zinc-200 font-semibold">{formatFloat(average_ast_depth, 1)}</span>
            </div>
            <div>
              <span className="text-zinc-500 block text-[9px] uppercase">Nesting</span>
              <span className="text-zinc-200 font-semibold">{formatFloat(average_control_nesting_depth, 1)}</span>
            </div>
          </div>
        </div>

        {/* Card 4: Halstead Science */}
        <div className="p-3.5 bg-zinc-900/60 border border-zinc-800/90 rounded-xl flex flex-col justify-between hover:border-zinc-700/80 transition shadow-xs">
          <div>
            <div className="flex items-center justify-between text-zinc-400 mb-1.5">
              <span className="text-[10px] font-medium uppercase tracking-wider text-zinc-400">
                Halstead Science
              </span>
              <Calculator className="w-3.5 h-3.5 text-cyan-400" />
            </div>
            <div className="flex items-baseline justify-between gap-1">
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold font-mono text-cyan-400">
                  {formatFloat(average_halstead_volume, 1)}
                </span>
                <span className="text-[11px] text-zinc-500 font-sans">
                  avg volume (V)
                </span>
              </div>
              <span className="text-[10px] text-zinc-500 font-mono shrink-0">
                {halstead_volume_evaluated_scopes} eval
              </span>
            </div>
          </div>

          <div className="mt-3 pt-2.5 border-t border-zinc-800/60 flex items-center justify-between text-[10px] font-mono">
            <span className="text-zinc-500">Effort (E):</span>
            <div className="flex items-center gap-1.5">
              <span className="text-zinc-300 font-semibold">
                {formatFloat(average_halstead_effort, 1)}
              </span>
              <span className="text-zinc-500 text-[9px] font-sans">
                ({halstead_effort_evaluated_scopes} effort-eval)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Diagnostics Banner if any scopes have partial or unclassified syntax */}
      {(partial_coverage_volume_scopes > 0 || unclassified_syntax_scopes > 0) && (
        <div className="px-3.5 py-2 rounded-lg bg-zinc-900/40 border border-zinc-800/60 flex items-center gap-2 text-[11px] text-zinc-400">
          <Info className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <span>
            Diagnostic notice: {partial_coverage_volume_scopes > 0 && `${partial_coverage_volume_scopes} scope(s) have partial Halstead coverage.`}{" "}
            {unclassified_syntax_scopes > 0 && `${unclassified_syntax_scopes} scope(s) contain unclassified Python syntax.`}{" "}
            Averages strictly preserve approved population denominators without numeric pollution.
          </span>
        </div>
      )}
    </div>
  );
};
