"use client";

import React, { useState, useMemo } from "react";
import { UnifiedScopeMetrics } from "@/types/analysis";
import { ScopeInspector } from "./ScopeInspector";
import {
  ArrowUpDown,
  RotateCcw,
} from "lucide-react";

interface ScopeMetricsTableProps {
  scopes: UnifiedScopeMetrics[] | null | undefined;
  selectedScopeId?: string | null;
  onSelectScope?: (scope: UnifiedScopeMetrics | null) => void;
}

type SortField =
  | "canonical"
  | "name"
  | "scope_type"
  | "lineno"
  | "cyclomatic"
  | "statements"
  | "depth"
  | "volume"
  | "effort";

type SortOrder = "asc" | "desc";

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

export const ScopeMetricsTable: React.FC<ScopeMetricsTableProps> = ({
  scopes,
  selectedScopeId: controlledSelectedScopeId,
  onSelectScope,
}) => {
  const [sortField, setSortField] = useState<SortField>("canonical");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [internalSelectedScopeId, setInternalSelectedScopeId] = useState<string | null>(null);

  const selectedScopeId =
    controlledSelectedScopeId !== undefined
      ? controlledSelectedScopeId
      : internalSelectedScopeId;

  // Derive selected scope directly from current scopes (clears automatically if scope no longer exists)
  const selectedScope = useMemo(() => {
    if (!selectedScopeId || !scopes) return null;
    return scopes.find((s) => s.scope_id === selectedScopeId) ?? null;
  }, [scopes, selectedScopeId]);

  const effectiveSelectedScopeId = selectedScope?.scope_id ?? null;

  const handleRowClick = (scope: UnifiedScopeMetrics) => {
    const nextId = effectiveSelectedScopeId === scope.scope_id ? null : scope.scope_id;
    setInternalSelectedScopeId(nextId);
    onSelectScope?.(nextId ? scope : null);
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      if (sortOrder === "asc") {
        setSortOrder("desc");
      } else {
        // Reset to canonical ordering
        setSortField("canonical");
        setSortOrder("asc");
      }
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  const sortedScopes = useMemo(() => {
    if (!scopes || scopes.length === 0) return [];
    if (sortField === "canonical") return scopes;

    const list = [...scopes];
    list.sort((a, b) => {
      let valA: string | number = 0;
      let valB: string | number = 0;

      switch (sortField) {
        case "name":
          valA = a.name.toLowerCase();
          valB = b.name.toLowerCase();
          break;
        case "scope_type":
          valA = a.scope_type;
          valB = b.scope_type;
          break;
        case "lineno":
          valA = a.lineno ?? 0;
          valB = b.lineno ?? 0;
          break;
        case "cyclomatic":
          valA = a.cyclomatic.cyclomatic_complexity ?? -1;
          valB = b.cyclomatic.cyclomatic_complexity ?? -1;
          break;
        case "statements":
          valA = a.structural.statement_count;
          valB = b.structural.statement_count;
          break;
        case "depth":
          valA = a.structural.ast_depth;
          valB = b.structural.ast_depth;
          break;
        case "volume":
          valA = a.halstead.volume ?? -1;
          valB = b.halstead.volume ?? -1;
          break;
        case "effort":
          valA = a.halstead.effort ?? -1;
          valB = b.halstead.effort ?? -1;
          break;
      }

      if (valA < valB) return sortOrder === "asc" ? -1 : 1;
      if (valA > valB) return sortOrder === "asc" ? 1 : -1;
      return 0;
    });

    return list;
  }, [scopes, sortField, sortOrder]);

  if (!scopes || scopes.length === 0) {
    return (
      <div className="p-6 bg-zinc-900/40 border border-zinc-800 rounded-xl text-center">
        <p className="text-xs text-zinc-500 font-mono">
          No per-scope metrics available. Submit a Python source snippet to inspect scopes.
        </p>
      </div>
    );
  }

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

  return (
    <div className="space-y-3">
      {/* Table Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100 tracking-tight">
              Per-Scope Metrics Explorer
            </h3>
            <span className="text-[10px] text-zinc-500 font-sans">
              (click row to inspect)
            </span>
          </div>
          <p className="text-[11px] text-zinc-400 mt-0.5">
            Deterministic scope inventory preserving canonical source order and AST boundaries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {sortField !== "canonical" && (
            <button
              onClick={() => {
                setSortField("canonical");
                setSortOrder("asc");
              }}
              className="px-2 py-1 rounded text-[11px] font-mono bg-zinc-800 text-zinc-300 hover:text-white border border-zinc-700 flex items-center gap-1 transition"
            >
              <RotateCcw className="w-3 h-3 text-zinc-400" />
              <span>Reset to Canonical Order</span>
            </button>
          )}
          <span className="text-[11px] font-mono text-zinc-500">
            {scopes.length} {scopes.length === 1 ? "scope" : "scopes"}
          </span>
        </div>
      </div>

      {/* Main Table Container with optimized column widths & mobile sticky first column */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900 text-zinc-400 text-[10px] uppercase tracking-wider font-semibold">
                {/* 1. Scope Identifier - Sticky Column */}
                <th className="py-2.5 px-2.5 min-w-[170px] sticky left-0 z-20 bg-zinc-900 border-r border-zinc-800/80 shadow-[2px_0_6px_-2px_rgba(0,0,0,0.6)]">
                  <button
                    onClick={() => handleSort("name")}
                    className="flex items-center gap-1 hover:text-zinc-200 transition"
                  >
                    <span>Scope / Identifier</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 2. Scope Type */}
                <th className="py-2.5 px-1.5 text-center min-w-[65px]">
                  <button
                    onClick={() => handleSort("scope_type")}
                    className="flex items-center gap-1 mx-auto hover:text-zinc-200 transition"
                  >
                    <span>Type</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 3. Lines */}
                <th className="py-2.5 px-1.5 text-center min-w-[60px]">
                  <button
                    onClick={() => handleSort("lineno")}
                    className="flex items-center gap-1 mx-auto hover:text-zinc-200 transition"
                  >
                    <span>Lines</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 4. Cyclomatic Complexity */}
                <th className="py-2.5 px-2 text-right min-w-[95px]">
                  <button
                    onClick={() => handleSort("cyclomatic")}
                    className="flex items-center gap-1 ml-auto hover:text-zinc-200 transition"
                  >
                    <span>Cyclomatic (M)</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 5. Statement Count */}
                <th className="py-2.5 px-1.5 text-right min-w-[55px]">
                  <button
                    onClick={() => handleSort("statements")}
                    className="flex items-center gap-1 ml-auto hover:text-zinc-200 transition"
                  >
                    <span>Stmts</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 6. AST Depth */}
                <th className="py-2.5 px-1.5 text-right min-w-[50px]">
                  <button
                    onClick={() => handleSort("depth")}
                    className="flex items-center gap-1 ml-auto hover:text-zinc-200 transition"
                  >
                    <span>Depth</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 7. Control Nesting */}
                <th className="py-2.5 px-1.5 text-right min-w-[50px]">
                  <span>Nesting</span>
                </th>

                {/* 8. Halstead Volume */}
                <th className="py-2.5 px-2 text-right min-w-[75px]">
                  <button
                    onClick={() => handleSort("volume")}
                    className="flex items-center gap-1 ml-auto hover:text-zinc-200 transition"
                  >
                    <span>Volume (V)</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 9. Halstead Difficulty */}
                <th className="py-2.5 px-1.5 text-right min-w-[70px]">
                  <span>Difficulty (D)</span>
                </th>

                {/* 10. Halstead Effort */}
                <th className="py-2.5 px-2 text-right min-w-[75px]">
                  <button
                    onClick={() => handleSort("effort")}
                    className="flex items-center gap-1 ml-auto hover:text-zinc-200 transition"
                  >
                    <span>Effort (E)</span>
                    <ArrowUpDown className="w-3 h-3 text-zinc-500" />
                  </button>
                </th>

                {/* 11. Syntax Coverage */}
                <th className="py-2.5 px-2 text-center min-w-[75px]">
                  <span>Coverage</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/60 font-mono">
              {sortedScopes.map((scope) => {
                const isSelected = effectiveSelectedScopeId === scope.scope_id;
                const cyclo = scope.cyclomatic;
                const struct = scope.structural;
                const hal = scope.halstead;

                const lineSpan =
                  scope.lineno != null
                    ? scope.end_lineno != null && scope.end_lineno !== scope.lineno
                      ? `L${scope.lineno}–L${scope.end_lineno}`
                      : `L${scope.lineno}`
                    : "—";

                return (
                  <tr
                    key={scope.scope_id}
                    tabIndex={0}
                    role="row"
                    aria-selected={isSelected}
                    onClick={() => handleRowClick(scope)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleRowClick(scope);
                      }
                    }}
                    className={`group cursor-pointer transition-colors focus:outline-hidden focus:ring-1 focus:ring-emerald-500/50 ${
                      isSelected
                        ? "bg-zinc-800/80 border-l-2 border-emerald-400"
                        : "hover:bg-zinc-800/40 bg-zinc-950/20 border-l-2 border-transparent"
                    }`}
                  >
                    {/* 1. Scope Name and Identifier - Sticky Column */}
                    <td
                      className={`py-2 px-2.5 sticky left-0 z-10 border-r border-zinc-800/80 shadow-[2px_0_6px_-2px_rgba(0,0,0,0.6)] transition-colors ${
                        isSelected
                          ? "bg-zinc-800"
                          : "bg-zinc-900 group-hover:bg-zinc-800"
                      }`}
                    >
                      <div className="flex flex-col">
                        <span
                          className={`font-semibold font-sans text-xs flex items-center gap-1.5 ${
                            isSelected ? "text-emerald-300" : "text-zinc-100"
                          }`}
                        >
                          {scope.name}
                        </span>
                        <span className="text-[10px] text-zinc-500 truncate max-w-[200px]">
                          {scope.scope_id}
                        </span>
                      </div>
                    </td>

                    {/* 2. Scope Type */}
                    <td className="py-2 px-1.5 text-center">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[10px] border font-sans font-medium uppercase tracking-wider ${getScopeTypeBadge(
                          scope.scope_type
                        )}`}
                      >
                        {scope.scope_type === "class_body" ? "class" : scope.scope_type}
                      </span>
                    </td>

                    {/* 3. Source Line Span */}
                    <td className="py-2 px-1.5 text-center text-[11px] text-zinc-400">
                      {lineSpan}
                    </td>

                    {/* 4. Cyclomatic Complexity */}
                    <td className="py-2 px-2 text-right">
                      {cyclo.cyclomatic_status === "COMPLETE" ? (
                        <div className="flex items-center justify-end gap-1.5">
                          {cyclo.is_provisional && (
                            <span className="px-1 py-0.2 rounded text-[9px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-sans">
                              Prov
                            </span>
                          )}
                          {cyclo.risk_rank && (
                            <span
                              className={`px-1 py-0.2 rounded text-[9px] font-bold border font-mono ${getRiskRankBadge(
                                cyclo.risk_rank
                              )}`}
                            >
                              {cyclo.risk_rank}
                            </span>
                          )}
                          <span className="font-bold text-zinc-100">
                            {cyclo.cyclomatic_complexity}
                          </span>
                        </div>
                      ) : (
                        <span className="inline-block px-1.5 py-0.2 rounded text-[10px] font-sans bg-zinc-800/80 text-zinc-400 border border-zinc-700/60">
                          {cyclo.cyclomatic_status}
                        </span>
                      )}
                    </td>

                    {/* 5. Statements */}
                    <td className="py-2 px-1.5 text-right text-zinc-300">
                      {formatInt(struct.statement_count)}
                    </td>

                    {/* 6. AST Depth */}
                    <td className="py-2 px-1.5 text-right text-zinc-400">
                      {struct.ast_depth}
                    </td>

                    {/* 7. Nesting Depth */}
                    <td className="py-2 px-1.5 text-right text-zinc-400">
                      {struct.control_nesting_depth}
                    </td>

                    {/* 8. Halstead Volume */}
                    <td className="py-2 px-2 text-right text-cyan-300">
                      {formatFloat(hal.volume, 1)}
                    </td>

                    {/* 9. Halstead Difficulty */}
                    <td className="py-2 px-1.5 text-right text-zinc-300">
                      {formatFloat(hal.difficulty, 1)}
                    </td>

                    {/* 10. Halstead Effort */}
                    <td className="py-2 px-2 text-right text-zinc-300">
                      {formatFloat(hal.effort, 1)}
                    </td>

                    {/* 11. Halstead Syntax Coverage */}
                    <td className="py-2 px-2 text-center">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-[9px] border font-sans font-medium uppercase tracking-wider ${getCoverageBadge(
                          hal.syntax_coverage_status
                        )}`}
                      >
                        {hal.syntax_coverage_status === "UNCLASSIFIED_SYNTAX"
                          ? "Unclassified"
                          : hal.syntax_coverage_status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 3. Detailed Scope Inspector */}
      {selectedScope && (
        <ScopeInspector
          scope={selectedScope}
          onClose={() => {
            setInternalSelectedScopeId(null);
            onSelectScope?.(null);
          }}
        />
      )}
    </div>
  );
};
