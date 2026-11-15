"use client";

import React from "react";
import { Clock, HardDrive, ShieldCheck, Zap, AlertTriangle, HelpCircle } from "lucide-react";
import { SpaceBreakdown } from "@/types/analysis";

interface ComplexityOverviewProps {
  timeComplexity: string;
  tightBound?: string;
  spaceComplexity: string;
  spaceBreakdown?: SpaceBreakdown;
  confidence: "HIGH" | "MEDIUM" | "LOW" | "UNSUPPORTED";
  maxNesting: number;
  analysisScope?: "module" | "function" | "function_collection" | "legacy_unknown" | null;
  analysisTarget?: string | null;
  analysisComplete?: boolean | null;
  analysisStatus?: "COMPLETE" | "PARTIAL" | "UNSUPPORTED" | "LEGACY_RECORD" | null;
  knownTimeComplexity?: string | null;
  knownSpaceComplexity?: string | null;
}

export const ComplexityOverview: React.FC<ComplexityOverviewProps> = ({
  timeComplexity,
  tightBound,
  spaceComplexity,
  spaceBreakdown,
  confidence,
  maxNesting,
  analysisScope,
  analysisTarget,
  analysisComplete = null,
  analysisStatus = null,
  knownTimeComplexity,
  knownSpaceComplexity,
}) => {
  // Helper for color coding Big-O
  const getTimeColor = (comp: string) => {
    if (comp.includes("Unknown")) {
      return {
        bg: "bg-amber-950/20 border-amber-500/40 text-amber-300",
        badge: "bg-amber-500/20 text-amber-300",
        label: "Partial / Unresolved",
      };
    }
    if (comp === "O(1)" || comp === "O(log n)") {
      return {
        bg: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
        badge: "bg-emerald-500/20 text-emerald-300",
        label: "Sub-linear / Optimal",
      };
    }
    if (comp === "O(n)") {
      return {
        bg: "bg-blue-500/10 border-blue-500/30 text-blue-400",
        badge: "bg-blue-500/20 text-blue-300",
        label: "Linear Scaling",
      };
    }
    if (comp === "O(n log n)") {
      return {
        bg: "bg-cyan-500/10 border-cyan-500/30 text-cyan-400",
        badge: "bg-cyan-500/20 text-cyan-300",
        label: "Linearithmic",
      };
    }
    if (comp === "O(n²)" || comp.includes("*")) {
      return {
        bg: "bg-amber-500/10 border-amber-500/30 text-amber-400",
        badge: "bg-amber-500/20 text-amber-300",
        label: "Quadratic / Multi-variable",
      };
    }
    if (comp === "O(n³)" || comp.includes("n⁴") || comp.includes("n^")) {
      return {
        bg: "bg-rose-500/10 border-rose-500/30 text-rose-400",
        badge: "bg-rose-500/20 text-rose-300",
        label: "Polynomial Scaling",
      };
    }
    if (comp.includes("2^n") || comp.includes("3^n") || comp.includes("^n")) {
      return {
        bg: "bg-purple-500/10 border-purple-500/30 text-purple-400",
        badge: "bg-purple-500/20 text-purple-300",
        label: "Exponential Growth",
      };
    }
    if (comp.includes("!")) {
      return {
        bg: "bg-red-500/10 border-red-500/30 text-red-400",
        badge: "bg-red-500/20 text-red-300",
        label: "Factorial Growth",
      };
    }
    if (comp.includes("Unsupported")) {
      return {
        bg: "bg-zinc-800/80 border-rose-500/40 text-rose-400",
        badge: "bg-rose-500/20 text-rose-300",
        label: "Unsupported Solver",
      };
    }
    return {
      bg: "bg-zinc-800 border-zinc-700 text-zinc-300",
      badge: "bg-zinc-700 text-zinc-300",
      label: "Analyzed Class",
    };
  };

  const timeStyle = getTimeColor(timeComplexity);

  const getConfidenceBadge = (conf: string) => {
    switch (conf) {
      case "HIGH":
        return {
          icon: <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />,
          color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
          text: "High Certainty",
        };
      case "MEDIUM":
        return {
          icon: <Zap className="w-3.5 h-3.5 text-amber-400" />,
          color: "text-amber-400 bg-amber-500/10 border-amber-500/20",
          text: "Medium Inferred",
        };
      case "UNSUPPORTED":
        return {
          icon: <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />,
          color: "text-rose-400 bg-rose-500/10 border-rose-500/20",
          text: "Unsupported Solver",
        };
      default:
        return {
          icon: <HelpCircle className="w-3.5 h-3.5 text-yellow-400" />,
          color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
          text: "Low / Bounded",
        };
    }
  };

  const confBadge = getConfidenceBadge(confidence);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {/* Time Complexity Card */}
      <div className={`p-4 rounded-xl border ${timeStyle.bg} flex flex-col justify-between transition-all`}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            <Clock className="w-4 h-4 text-zinc-400" />
            <span>Time Complexity</span>
          </div>
          <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${timeStyle.badge}`}>
            {timeStyle.label}
          </span>
        </div>
        <div>
          <div className="text-3xl font-mono font-bold tracking-tight mb-1 text-white">
            {timeComplexity}
          </div>
          {knownTimeComplexity && timeComplexity.includes("Unknown") && (
            <div className="text-xs font-mono text-zinc-300 font-medium mb-1">
              Known work: <span className="text-emerald-400 font-bold">{knownTimeComplexity}</span> (total unproven)
            </div>
          )}
          {tightBound && (
            <div className="text-xs font-mono text-emerald-400/90 font-semibold mb-1">
              Tight Bound: {tightBound}
            </div>
          )}
          <p className="text-xs text-zinc-400">
            Worst-case execution cost derived symbolically.
          </p>
        </div>
      </div>

      {/* Space Complexity Card with Detailed Breakdown */}
      <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            <HardDrive className="w-4 h-4 text-zinc-400" />
            <span>Space Complexity</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-medium bg-zinc-800 text-zinc-300">
            Total: {spaceComplexity}
            {knownSpaceComplexity && spaceComplexity.includes("Unknown") && ` (Known: ${knownSpaceComplexity})`}
          </span>
        </div>
        <div className="space-y-1.5 text-xs">
          {spaceBreakdown ? (
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 font-mono text-[11px] pt-1">
              <div className="flex justify-between border-b border-zinc-800/80 pb-0.5">
                <span className="text-zinc-400">Auxiliary:</span>
                <span className="text-zinc-200 font-semibold">{spaceBreakdown.auxiliary}</span>
              </div>
              <div className="flex justify-between border-b border-zinc-800/80 pb-0.5">
                <span className="text-zinc-400">Stack:</span>
                <span className="text-zinc-200 font-semibold">{spaceBreakdown.recursion_stack}</span>
              </div>
              <div className="flex justify-between pt-0.5">
                <span className="text-zinc-400">Output:</span>
                <span className="text-zinc-200 font-semibold">{spaceBreakdown.output}</span>
              </div>
              <div className="flex justify-between pt-0.5">
                <span className="text-zinc-400">Retained:</span>
                <span className="text-emerald-400 font-bold">{spaceBreakdown.total_retained}</span>
              </div>
            </div>
          ) : (
            <div className="text-2xl font-mono font-bold text-white mb-1">
              {spaceComplexity}
            </div>
          )}
          <p className="text-[11px] text-zinc-400 mt-1">
            Separates auxiliary memory, recursion stack, and output buffers.
          </p>
        </div>
      </div>

      {/* Confidence & Structural Factor Card */}
      <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/60 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <div className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Static Confidence
          </div>
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-medium ${confBadge.color}`}>
            {confBadge.icon}
            <span>{confBadge.text}</span>
          </div>
        </div>
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-zinc-400">Analysis Scope:</span>
            <span className="text-xs font-medium text-zinc-200">
              {analysisScope === "module" && "Module Scope"}
              {analysisScope === "function" && (analysisTarget ? `Function (${analysisTarget})` : "Function Scope")}
              {analysisScope === "function_collection" && (analysisTarget ? `Dominant: ${analysisTarget}` : "Function Collection")}
              {!analysisScope && "AST Static Scope"}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-zinc-400">Max Nesting Depth:</span>
            <span className="text-sm font-mono font-bold text-zinc-200">{maxNesting} levels</span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-zinc-400">Analysis Status:</span>
            <span
              className={`text-xs font-medium ${
                analysisStatus === "COMPLETE"
                  ? "text-emerald-400"
                  : analysisStatus === "LEGACY_RECORD" || analysisComplete === null
                  ? "text-zinc-400 font-mono"
                  : analysisStatus === "UNSUPPORTED"
                  ? "text-rose-400"
                  : "text-amber-400"
              }`}
            >
              {analysisStatus === "COMPLETE" && "Complete AST Derivation"}
              {analysisStatus === "PARTIAL" && "Incomplete (Conservative Bound)"}
              {analysisStatus === "UNSUPPORTED" && "Unsupported Model"}
              {(analysisStatus === "LEGACY_RECORD" || (!analysisStatus && analysisComplete === null)) && "Legacy Analysis (Pre-Phase 1A)"}
              {!analysisStatus && analysisComplete === true && "Complete AST Derivation"}
              {!analysisStatus && analysisComplete === false && "Incomplete (Conservative Bound)"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
