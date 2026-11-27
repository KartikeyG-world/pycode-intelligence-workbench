"use client";

import React, { useState } from "react";
import { UnifiedScopeMetrics } from "@/types/analysis";
import {
  X,
  GitBranch,
  Layers,
  Calculator,
  AlertTriangle,
  Info,
  ChevronDown,
  ChevronUp,
  Check,
  Copy,
  Binary,
} from "lucide-react";

interface ScopeInspectorProps {
  scope: UnifiedScopeMetrics;
  onClose?: () => void;
}

type InspectorTab = "cyclomatic" | "structural" | "halstead";

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
  if (!Number.isFinite(val)) return "—";
  return val.toLocaleString("en-US");
}

export const ScopeInspector: React.FC<ScopeInspectorProps> = ({ scope, onClose }) => {
  const [activeTab, setActiveTab] = useState<InspectorTab>("cyclomatic");
  const [copiedId, setCopiedId] = useState(false);
  const [showAllOperators, setShowAllOperators] = useState(false);
  const [showAllOperands, setShowAllOperands] = useState(false);

  const cyclo = scope.cyclomatic;
  const struct = scope.structural;
  const hal = scope.halstead;

  // Sort copied inventory arrays without mutating backend response
  const sortedOperators = Object.entries(hal.operator_inventory || {}).sort((a, b) => b[1] - a[1]);
  const sortedOperands = Object.entries(hal.operand_inventory || {}).sort((a, b) => b[1] - a[1]);
  const decisionPointEntries = Object.entries(cyclo.decision_points || {}).sort((a, b) => b[1] - a[1]);

  const handleCopyId = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      void navigator.clipboard.writeText(scope.scope_id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  const lineSpan =
    scope.lineno != null
      ? scope.end_lineno != null && scope.end_lineno !== scope.lineno
        ? `Lines ${scope.lineno}–${scope.end_lineno}`
        : `Line ${scope.lineno}`
      : "Line —";

  const getScopeTypeBadge = (type: string) => {
    switch (type) {
      case "module":
        return "bg-zinc-800 text-zinc-300 border-zinc-700";
      case "function":
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
      case "method":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "class_body":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  const getCycloStatusBadge = (status: string) => {
    switch (status) {
      case "COMPLETE":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "PARTIAL":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "UNSUPPORTED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  const getCoverageBadge = (status: string) => {
    switch (status) {
      case "FULL":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "PARTIAL":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "UNCLASSIFIED_SYNTAX":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  const getRiskRankBadge = (rank?: string | null) => {
    if (!rank) return null;
    switch (rank) {
      case "A":
        return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
      case "B":
        return "bg-teal-500/15 text-teal-300 border-teal-500/30";
      case "C":
        return "bg-amber-500/15 text-amber-300 border-amber-500/30";
      case "D":
        return "bg-orange-500/15 text-orange-300 border-orange-500/30";
      case "E":
      case "F":
        return "bg-rose-500/15 text-rose-300 border-rose-500/30";
      default:
        return "bg-zinc-800 text-zinc-400 border-zinc-700";
    }
  };

  return (
    <div
      role="region"
      aria-label={`Detailed Scope Inspector for ${scope.name}`}
      className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/90 shadow-lg overflow-hidden transition-all duration-200"
    >
      {/* 1. Scope Overview Header */}
      <div className="p-4 bg-zinc-900/80 border-b border-zinc-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="text-base font-bold text-zinc-100 font-sans tracking-tight">
              {scope.name}
            </h4>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium uppercase tracking-wider border ${getScopeTypeBadge(
                scope.scope_type
              )}`}
            >
              {scope.scope_type === "class_body" ? "class" : scope.scope_type}
            </span>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono text-zinc-400 bg-zinc-800/80 border border-zinc-700/60">
              {lineSpan}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium uppercase tracking-wider border ${getCycloStatusBadge(
                cyclo.cyclomatic_status
              )}`}
            >
              CFG: {cyclo.cyclomatic_status}
            </span>
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-sans font-medium uppercase tracking-wider border ${getCoverageBadge(
                hal.syntax_coverage_status
              )}`}
            >
              Coverage: {hal.syntax_coverage_status}
            </span>
          </div>

          {/* Canonical Scope ID with copy button */}
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[11px] font-mono text-zinc-500">scope_id:</span>
            <code className="text-[11px] font-mono text-zinc-300 bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800 select-all">
              {scope.scope_id}
            </code>
            <button
              onClick={handleCopyId}
              title="Copy canonical scope ID"
              aria-label="Copy canonical scope ID"
              className="p-1 rounded text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 transition"
            >
              {copiedId ? (
                <Check className="w-3 h-3 text-emerald-400" />
              ) : (
                <Copy className="w-3 h-3" />
              )}
            </button>
          </div>
        </div>

        {/* Close Button */}
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close Scope Inspector"
            className="self-end sm:self-center p-1.5 rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition border border-transparent hover:border-zinc-700"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Primary KPI Summary Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-y sm:divide-y-0 divide-zinc-800/80 bg-zinc-900/40 border-b border-zinc-800/80 text-xs">
        {/* Cyclomatic Metric */}
        <div className="p-3 flex flex-col justify-between">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Cyclomatic Complexity
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-bold font-mono text-emerald-400">
              {cyclo.cyclomatic_status === "COMPLETE"
                ? formatInt(cyclo.cyclomatic_complexity)
                : "—"}
            </span>
            {cyclo.risk_rank && (
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] font-bold border font-mono ${getRiskRankBadge(
                  cyclo.risk_rank
                )}`}
              >
                Rank {cyclo.risk_rank}
              </span>
            )}
            {cyclo.is_provisional && (
              <span className="px-1 py-0.2 rounded text-[9px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-sans">
                Prov
              </span>
            )}
          </div>
        </div>

        {/* Statements */}
        <div className="p-3 flex flex-col justify-between">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Statements & Depth
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-bold font-mono text-zinc-100">
              {formatInt(struct.statement_count)}
            </span>
            <span className="text-[11px] text-zinc-500 font-mono">
              stmts / d={struct.ast_depth}
            </span>
          </div>
        </div>

        {/* Halstead Volume */}
        <div className="p-3 flex flex-col justify-between">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Halstead Volume (V)
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-bold font-mono text-cyan-400">
              {formatFloat(hal.volume, 1)}
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">
              {hal.volume_status === "AVAILABLE" ? "bits" : "undef"}
            </span>
          </div>
        </div>

        {/* Halstead Effort */}
        <div className="p-3 flex flex-col justify-between">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
            Halstead Effort (E)
          </span>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-xl font-bold font-mono text-zinc-200">
              {formatFloat(hal.effort, 1)}
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">
              diff={formatFloat(hal.difficulty, 1)}
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-1 px-4 py-2 bg-zinc-900/60 border-b border-zinc-800">
        <button
          onClick={() => setActiveTab("cyclomatic")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeTab === "cyclomatic"
              ? "bg-zinc-800 text-emerald-400 border border-zinc-700 shadow-xs"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <GitBranch className="w-3.5 h-3.5" />
          <span>Control Flow & Cyclomatic</span>
        </button>

        <button
          onClick={() => setActiveTab("structural")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeTab === "structural"
              ? "bg-zinc-800 text-amber-400 border border-zinc-700 shadow-xs"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>AST Structure ({struct.statement_count} stmts)</span>
        </button>

        <button
          onClick={() => setActiveTab("halstead")}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            activeTab === "halstead"
              ? "bg-zinc-800 text-cyan-400 border border-zinc-700 shadow-xs"
              : "text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Calculator className="w-3.5 h-3.5" />
          <span>Halstead Science & Tokens</span>
        </button>
      </div>

      {/* Tab Content Body */}
      <div className="p-4 sm:p-5">
        {/* ================================================================= */}
        {/* TAB 1: CYCLOMATIC COMPLEXITY & CONTROL-FLOW DIAGNOSTICS */}
        {/* ================================================================= */}
        {activeTab === "cyclomatic" && (
          <div className="space-y-4">
            {/* Primary & Calculation Breakdown Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* CFG Graph Structure */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300 mb-2.5">
                  <GitBranch className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Control Flow Graph Properties</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Total Nodes:</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(cyclo.total_nodes)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Total Edges:</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(cyclo.total_edges)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Reachable Nodes:</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(cyclo.reachable_nodes)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Reachable Edges:</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(cyclo.reachable_edges)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between col-span-2">
                    <span className="text-zinc-500">Unreachable Basic Blocks:</span>
                    <span
                      className={`font-semibold ${
                        cyclo.unreachable_basic_blocks > 0 ? "text-amber-400" : "text-zinc-200"
                      }`}
                    >
                      {formatInt(cyclo.unreachable_basic_blocks)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Cyclomatic Calculations & Discrepancy */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300 mb-2.5">
                  <Binary className="w-3.5 h-3.5 text-indigo-400" />
                  <span>Calculations & Verification</span>
                </div>
                <div className="space-y-2 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <span className="text-zinc-500">Graph Cyclomatic (E - N + 2P):</span>
                    <span className="text-zinc-200 font-semibold">
                      {formatInt(cyclo.graph_cyclomatic)}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <span className="text-zinc-500">Decision Cyclomatic (π + 1):</span>
                    <span className="text-zinc-200 font-semibold">
                      {formatInt(cyclo.decision_cyclomatic)}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <span className="text-zinc-500">Formula Discrepancy:</span>
                    <span
                      className={`font-semibold ${
                        cyclo.cyclomatic_discrepancy && cyclo.cyclomatic_discrepancy !== 0
                          ? "text-rose-400"
                          : "text-emerald-400"
                      }`}
                    >
                      {cyclo.cyclomatic_discrepancy != null
                        ? cyclo.cyclomatic_discrepancy
                        : "0"}
                    </span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <span className="text-zinc-500">Risk Assessment:</span>
                    <div className="flex items-center gap-1.5">
                      {cyclo.risk_rank ? (
                        <span
                          className={`px-1.5 py-0.2 rounded text-[10px] font-bold border font-mono ${getRiskRankBadge(
                            cyclo.risk_rank
                          )}`}
                        >
                          Rank {cyclo.risk_rank}
                        </span>
                      ) : (
                        <span className="text-zinc-500">—</span>
                      )}
                      {cyclo.is_provisional && (
                        <span className="text-[10px] text-amber-400 font-sans">(Provisional)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Decision Points Breakdown */}
            <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300">
                  Decision Points Breakdown ({decisionPointEntries.length} types)
                </span>
                <span className="text-[11px] font-mono text-zinc-500">
                  Total: {decisionPointEntries.reduce((acc, curr) => acc + curr[1], 0)} points
                </span>
              </div>
              {decisionPointEntries.length > 0 ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
                  {decisionPointEntries.map(([point, count]) => (
                    <div
                      key={point}
                      className="p-2 rounded bg-zinc-900/90 border border-zinc-800 flex items-center justify-between text-xs font-mono"
                    >
                      <span className="text-zinc-400 truncate mr-1">{point}</span>
                      <span className="text-emerald-400 font-bold">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500 italic font-mono">
                  No decision points recorded in this scope.
                </p>
              )}
            </div>

            {/* Limitations Notice */}
            {cyclo.limitations && cyclo.limitations.length > 0 && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 space-y-1 text-xs text-amber-300">
                <div className="flex items-center gap-1.5 font-semibold text-amber-200">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>Control-Flow Limitations Recorded</span>
                </div>
                <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-300/90 pl-1">
                  {cyclo.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 2: STRUCTURAL METRICS & STATEMENT SUITES */}
        {/* ================================================================= */}
        {activeTab === "structural" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {/* Card 1: Statement Suite Composition */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2 text-xs font-mono">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 block">
                  Statement Suite
                </span>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Total Statements:</span>
                  <span className="text-zinc-100 font-bold">{formatInt(struct.statement_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Top-Level Statements:</span>
                  <span className="text-zinc-200 font-semibold">{formatInt(struct.top_level_statement_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Assertions:</span>
                  <span className="text-zinc-200">{formatInt(struct.assertion_count)}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Comprehensions:</span>
                  <span className="text-zinc-200">{formatInt(struct.comprehension_count)}</span>
                </div>
              </div>

              {/* Card 2: Tree Complexity */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2 text-xs font-mono">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 block">
                  AST Syntax Tree
                </span>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">AST Node Count:</span>
                  <span className="text-zinc-100 font-bold">{formatInt(struct.ast_node_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Max AST Depth:</span>
                  <span className="text-zinc-200 font-semibold">{formatInt(struct.ast_depth)}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Control Nesting Depth:</span>
                  <span className="text-zinc-200 font-semibold">{formatInt(struct.control_nesting_depth)}</span>
                </div>
              </div>

              {/* Card 3: Branching & Conditionals */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2 text-xs font-mono">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 block">
                  Branching & Logic
                </span>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">If Statements:</span>
                  <span className="text-zinc-200">{formatInt(struct.if_statement_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">If Expressions (Ternary):</span>
                  <span className="text-zinc-200">{formatInt(struct.if_expression_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Total Conditionals:</span>
                  <span className="text-zinc-100 font-semibold">{formatInt(struct.conditional_count)}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Boolean Operators:</span>
                  <span className="text-zinc-200">{formatInt(struct.boolean_operator_count)}</span>
                </div>
              </div>

              {/* Card 4: Loops & Interface */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2 text-xs font-mono">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 block">
                  Loops & Interface
                </span>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Loop Count:</span>
                  <span className="text-zinc-100 font-semibold">{formatInt(struct.loop_count)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-zinc-800/60">
                  <span className="text-zinc-400">Parameters:</span>
                  <span className="text-zinc-200">{formatInt(struct.parameter_count)}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-zinc-400">Return Statements:</span>
                  <span className="text-zinc-200">{formatInt(struct.return_count)}</span>
                </div>
              </div>
            </div>

            {/* Structural Diagnostics */}
            {struct.diagnostics && struct.diagnostics.length > 0 ? (
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-1.5 text-xs text-zinc-300">
                <div className="flex items-center gap-1.5 font-semibold text-zinc-200">
                  <Info className="w-3.5 h-3.5 text-amber-400" />
                  <span>Structural Diagnostics ({struct.diagnostics.length})</span>
                </div>
                <ul className="list-disc list-inside space-y-1 text-zinc-400 font-mono text-[11px] pl-1">
                  {struct.diagnostics.map((diag, i) => (
                    <li key={i}>{diag}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-zinc-900/30 border border-zinc-800/60 text-xs text-zinc-500 font-mono">
                No structural diagnostic issues recorded.
              </div>
            )}
          </div>
        )}

        {/* ================================================================= */}
        {/* TAB 3: HALSTEAD COMPLEXITY & TOKEN ANALYSIS */}
        {/* ================================================================= */}
        {activeTab === "halstead" && (
          <div className="space-y-4">
            {/* Mathematical Halstead Metrics & Token Quantities */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Mathematical Metrics */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2.5">
                <span className="text-xs font-semibold text-zinc-300 block">
                  Halstead Mathematical Metrics
                </span>
                <div className="space-y-1.5 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <div>
                      <span className="text-zinc-400 font-semibold">Volume (V):</span>
                      <span className="text-[10px] text-zinc-500 block">V = N × log₂(η)</span>
                    </div>
                    <div className="text-right">
                      <span className="text-cyan-400 font-bold">{formatFloat(hal.volume, 2)}</span>
                      <span className="text-[10px] text-zinc-500 block">
                        {hal.volume_status}
                      </span>
                    </div>
                  </div>

                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <div>
                      <span className="text-zinc-400 font-semibold">Difficulty (D):</span>
                      <span className="text-[10px] text-zinc-500 block">D = (n₁ / 2) × (N₂ / n₂)</span>
                    </div>
                    <div className="text-right">
                      <span className="text-zinc-200 font-bold">{formatFloat(hal.difficulty, 2)}</span>
                      <span className="text-[10px] text-zinc-500 block">
                        {hal.difficulty_status}
                      </span>
                    </div>
                  </div>

                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between items-center">
                    <div>
                      <span className="text-zinc-400 font-semibold">Effort (E):</span>
                      <span className="text-[10px] text-zinc-500 block">E = D × V</span>
                    </div>
                    <div className="text-right">
                      <span className="text-zinc-200 font-bold">{formatFloat(hal.effort, 2)}</span>
                      <span className="text-[10px] text-zinc-500 block">
                        {hal.effort_status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Token Counts & Quantities */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80 space-y-2.5">
                <span className="text-xs font-semibold text-zinc-300 block">
                  Token Quantities & Vocabulary
                </span>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Distinct Operators (n₁):</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(hal.distinct_operators)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Distinct Operands (n₂):</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(hal.distinct_operands)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Total Operators (N₁):</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(hal.total_operators)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Total Operands (N₂):</span>
                    <span className="text-zinc-200 font-semibold">{formatInt(hal.total_operands)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Vocabulary (η = n₁ + n₂):</span>
                    <span className="text-cyan-400 font-bold">{formatInt(hal.vocabulary)}</span>
                  </div>
                  <div className="p-2 rounded bg-zinc-900/80 border border-zinc-800 flex justify-between">
                    <span className="text-zinc-500">Length (N = N₁ + N₂):</span>
                    <span className="text-zinc-100 font-bold">{formatInt(hal.length)}</span>
                  </div>
                </div>

                {/* Theoretical Estimates with prominent model disclaimer */}
                <div className="p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800 text-[11px] font-mono space-y-1">
                  <div className="flex justify-between text-zinc-400">
                    <span>Theoretical Time (T = E / 18):</span>
                    <span className="text-zinc-200 font-semibold">
                      {hal.theoretical_time_seconds != null
                        ? `${formatFloat(hal.theoretical_time_seconds, 2)}s`
                        : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between text-zinc-400">
                    <span>Theoretical Bugs (B = V / 3000):</span>
                    <span className="text-zinc-200 font-semibold">
                      {formatFloat(hal.theoretical_delivered_bugs, 3)}
                    </span>
                  </div>
                  <p className="text-[10px] text-zinc-500 pt-1 font-sans border-t border-zinc-800/60">
                    * Theoretical software science model estimates. Not measured execution time, runtime profiling, or verified bug counts.
                  </p>
                </div>
              </div>
            </div>

            {/* Syntax Coverage & Unclassified Elements */}
            {hal.unclassified_syntax_nodes && hal.unclassified_syntax_nodes.length > 0 && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 space-y-2 text-xs">
                <div className="flex items-center gap-1.5 font-semibold text-amber-200">
                  <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>
                    Unclassified Syntax Elements ({hal.unclassified_syntax_nodes.length})
                  </span>
                </div>
                <div className="divide-y divide-amber-500/10 font-mono text-[11px]">
                  {hal.unclassified_syntax_nodes.map((node, i) => (
                    <div key={i} className="py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-amber-300">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-amber-100">{node.node_class}</span>
                        <span className="text-zinc-400 text-[10px]">
                          {node.lineno != null ? `Line ${node.lineno}` : "Line —"}
                          {node.col_offset != null ? `:${node.col_offset}` : ""}
                        </span>
                      </div>
                      <span className="text-zinc-400 text-[10px] font-sans italic">{node.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Operator & Operand Token Inventories */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Operator Inventory */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-300">
                    Operator Inventory ({sortedOperators.length} distinct)
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500">
                    {formatInt(hal.total_operators)} total
                  </span>
                </div>
                {sortedOperators.length > 0 ? (
                  <div className="space-y-1">
                    <div className="grid grid-cols-2 gap-1.5 font-mono text-xs max-h-52 overflow-y-auto pr-1">
                      {(showAllOperators ? sortedOperators : sortedOperators.slice(0, 10)).map(
                        ([op, count]) => (
                          <div
                            key={op}
                            className="px-2 py-1 rounded bg-zinc-900/90 border border-zinc-800 flex items-center justify-between"
                          >
                            <span className="text-zinc-400 truncate mr-1" title={op}>
                              {op}
                            </span>
                            <span className="text-cyan-400 font-bold">{count}</span>
                          </div>
                        )
                      )}
                    </div>
                    {sortedOperators.length > 10 && (
                      <button
                        onClick={() => setShowAllOperators(!showAllOperators)}
                        className="text-[11px] text-zinc-400 hover:text-zinc-200 mt-2 flex items-center gap-1 transition"
                      >
                        {showAllOperators ? (
                          <>
                            <ChevronUp className="w-3 h-3" /> Show fewer operators
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3 h-3" /> Show all {sortedOperators.length} operators
                          </>
                        )}
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-zinc-500 italic font-mono">
                    No operators observed in this scope.
                  </p>
                )}
              </div>

              {/* Operand Inventory */}
              <div className="p-3.5 rounded-xl bg-zinc-900/40 border border-zinc-800/80">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-zinc-300">
                    Operand Inventory ({sortedOperands.length} distinct)
                  </span>
                  <span className="text-[11px] font-mono text-zinc-500">
                    {formatInt(hal.total_operands)} total
                  </span>
                </div>
                {sortedOperands.length > 0 ? (
                  <div className="space-y-1">
                    <div className="grid grid-cols-2 gap-1.5 font-mono text-xs max-h-52 overflow-y-auto pr-1">
                      {(showAllOperands ? sortedOperands : sortedOperands.slice(0, 10)).map(
                        ([operand, count]) => (
                          <div
                            key={operand}
                            className="px-2 py-1 rounded bg-zinc-900/90 border border-zinc-800 flex items-center justify-between"
                          >
                            <span className="text-zinc-400 truncate mr-1" title={operand}>
                              {operand}
                            </span>
                            <span className="text-emerald-400 font-bold">{count}</span>
                          </div>
                        )
                      )}
                    </div>
                    {sortedOperands.length > 10 && (
                      <button
                        onClick={() => setShowAllOperands(!showAllOperands)}
                        className="text-[11px] text-zinc-400 hover:text-zinc-200 mt-2 flex items-center gap-1 transition"
                      >
                        {showAllOperands ? (
                          <>
                            <ChevronUp className="w-3 h-3" /> Show fewer operands
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3 h-3" /> Show all {sortedOperands.length} operands
                          </>
                        )}
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-zinc-500 italic font-mono">
                    No operands observed in this scope.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
