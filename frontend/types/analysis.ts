export interface SyntaxErrorInfo {
  line: number;
  column: number;
  message: string;
  snippet?: string;
}

export interface CodeStatistics {
  function_count: number;
  loop_count: number;
  for_loop_count: number;
  while_loop_count: number;
  conditional_count: number;
  max_nesting_depth: number;
  recursion_detected: boolean;
  recursion_count: number;
  operation_count: number;
  comprehension_count: number;
  imported_modules: string[];
}

export interface CodeStructureNode {
  id: string;
  label: string;
  node_type: string;
  line?: number;
  complexity?: string;
  details?: string;
}

export interface CodeStructureEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

export interface CodeStructureData {
  nodes: CodeStructureNode[];
  edges: CodeStructureEdge[];
}

export interface SpaceBreakdown {
  auxiliary: string;
  recursion_stack: string;
  output: string;
  total_retained: string;
  peak_live_heap?: string;
  active_frames?: string;
  cache_retained?: string;
}

export interface RecurrenceInfo {
  present: boolean;
  expression?: string;
  is_solved: boolean;
  branching_factor: number;
  total_call_sites: number;
  derivation_steps: string[];
}

export interface TheoreticalGraphData {
  active_complexity: string;
  growth_points: Record<string, unknown>[];
  disclaimer: string;
}

export interface UnresolvedCallInfo {
  callee_name: string;
  line_number: number;
  reason: string;
}

export interface UnresolvedCostInfo {
  operation: string;
  line?: number;
  context?: string;
  loop_depth?: number;
  reason?: string;
}

export interface AnalyzeResponse {
  success: boolean;
  time_complexity: string;
  tight_bound?: string;
  space_complexity: string;
  space_breakdown?: SpaceBreakdown;
  confidence: "HIGH" | "MEDIUM" | "LOW" | "UNSUPPORTED";
  confidence_reasons?: string[];
  complexity_reasoning: string;
  recurrence?: RecurrenceInfo;
  statistics: CodeStatistics;
  detected_patterns: string[];
  optimization_suggestions: string[];
  structure: CodeStructureData;
  graph: TheoreticalGraphData;
  functions: Record<string, unknown>[];
  loops: Record<string, unknown>[];
  recursion: Record<string, unknown>;
  analysis_scope?: "module" | "function" | "function_collection" | "legacy_unknown" | null;
  analysis_target?: string | null;
  function_analyses?: Record<string, unknown>[];
  call_graph_complete?: boolean | null;
  cost_model_complete?: boolean | null;
  analysis_complete?: boolean | null;
  analysis_status?: "COMPLETE" | "PARTIAL" | "UNSUPPORTED" | "LEGACY_RECORD" | null;
  analysis_schema_version?: string | null;
  known_time_complexity?: string | null;
  known_space_complexity?: string | null;
  unresolved_costs?: UnresolvedCostInfo[];
  unresolved_calls?: UnresolvedCallInfo[];
  unsupported_patterns?: string[];
  limitations?: string[];
  call_graph?: Record<string, unknown>;
  error?: SyntaxErrorInfo;
  submission_id?: string;
  persistence_status?: "saved" | "failed" | "skipped" | null;
  persistence_warning?: string | null;
  scope_metrics?: UnifiedScopeMetrics[];
  project_metrics?: ProjectMetricsSummary | null;
}

// ============================================================================
// Phase 1B.2 / Phase 1C: Metrics Type Contracts
// ============================================================================

export interface UnclassifiedSyntaxRecord {
  node_class: string;
  lineno?: number | null;
  col_offset?: number | null;
  reason: string;
}

export interface ScopeStructuralMetrics {
  statement_count: number;
  top_level_statement_count: number;
  ast_node_count: number;
  ast_depth: number;
  control_nesting_depth: number;
  if_statement_count: number;
  if_expression_count: number;
  conditional_count: number;
  boolean_operator_count: number;
  assertion_count: number;
  loop_count: number;
  comprehension_count: number;
  parameter_count?: number | null;
  return_count?: number | null;
  diagnostics: string[];
}

export interface ScopeHalsteadMetrics {
  distinct_operators: number;
  distinct_operands: number;
  total_operators: number;
  total_operands: number;
  vocabulary: number;
  length: number;
  volume?: number | null;
  difficulty?: number | null;
  effort?: number | null;
  theoretical_time_seconds?: number | null;
  theoretical_delivered_bugs?: number | null;
  volume_status: "AVAILABLE" | "UNDEFINED_EMPTY_VOCABULARY";
  difficulty_status: "AVAILABLE" | "UNDEFINED_ZERO_OPERANDS";
  effort_status: "AVAILABLE" | "UNDEFINED_DEPENDENCY";
  undefined_reasons: string[];
  syntax_coverage_status: "FULL" | "PARTIAL" | "UNCLASSIFIED_SYNTAX";
  unclassified_syntax_nodes: UnclassifiedSyntaxRecord[];
  operator_inventory: Record<string, number>;
  operand_inventory: Record<string, number>;
}

export interface ScopeCyclomaticMetrics {
  cyclomatic_status: "COMPLETE" | "PARTIAL" | "UNSUPPORTED";
  cyclomatic_complexity?: number | null;
  graph_cyclomatic?: number | null;
  decision_cyclomatic?: number | null;
  cyclomatic_discrepancy?: number | null;
  risk_rank?: "A" | "B" | "C" | "D" | "E" | "F" | null;
  is_provisional: boolean;
  total_nodes: number;
  total_edges: number;
  reachable_nodes: number;
  reachable_edges: number;
  unreachable_basic_blocks: number;
  decision_points: Record<string, number>;
  limitations: string[];
}

export interface UnifiedScopeMetrics {
  scope_id: string;
  name: string;
  scope_type: "module" | "function" | "method" | "class_body";
  lineno?: number | null;
  end_lineno?: number | null;
  cyclomatic: ScopeCyclomaticMetrics;
  structural: ScopeStructuralMetrics;
  halstead: ScopeHalsteadMetrics;
}

export interface CorrelationDataPoint {
  scope_id: string;
  cyclomatic_complexity: number;
  metric_value: number;
}

export interface CorrelationDimension {
  dimension_name: string;
  pearson_r?: number | null;
  spearman_rho?: number | null;
  sample_size: number;
  status: "DESCRIPTIVE_ONLY" | "INSUFFICIENT_SAMPLE" | "ZERO_VARIANCE";
  diagnostic_message?: string | null;
  pairs: CorrelationDataPoint[];
}

export interface ProjectCorrelationReport {
  eligible_scope_count: number;
  dimensions: Record<string, CorrelationDimension>;
  disclaimer: string;
}

export interface ProjectMetricsSummary {
  total_scopes: number;
  procedural_scopes: number;
  module_scopes: number;
  class_scopes: number;
  average_statement_count?: number | null;
  average_ast_depth?: number | null;
  average_control_nesting_depth?: number | null;
  average_cyclomatic_complexity?: number | null;
  cyclomatic_evaluated_scopes: number;
  average_halstead_volume?: number | null;
  average_halstead_effort?: number | null;
  halstead_volume_evaluated_scopes: number;
  halstead_effort_evaluated_scopes: number;
  partial_coverage_volume_scopes: number;
  average_partial_halstead_volume?: number | null;
  partial_coverage_effort_scopes: number;
  average_partial_halstead_effort?: number | null;
  unclassified_syntax_scopes: number;
  correlation: ProjectCorrelationReport;
}

export interface HistoryItem {
  id: string;
  submission_id: string;
  title: string;
  code_snippet: string;
  time_complexity: string;
  space_complexity: string;
  confidence: string;
  created_at: string;
}

export interface HistoryDetail extends HistoryItem {
  code: string;
  complexity_reasoning: string;
  statistics: CodeStatistics;
  structure: CodeStructureData;
  graph_data: TheoreticalGraphData;
  detected_patterns: string[];
  optimization_suggestions: string[];
}
