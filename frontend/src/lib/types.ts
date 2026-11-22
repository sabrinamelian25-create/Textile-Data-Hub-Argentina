export interface CategorySummary {
  code: string;
  name: string;
  short_description: string;
  order: number;
  verified_series_count: number;
}

export interface LatestSummary {
  latest_date: string | null;
  latest_value: number | null;
  mom_pct: number | null;
  yoy_pct: number | null;
  is_preliminary: boolean;
}

export interface SeriesCard {
  series_id: number;
  series_code: string;
  series_name: string;
  short_name: string;
  description: string;
  unit: string;
  base_period: string | null;
  frequency: "DAILY" | "MONTHLY" | "QUARTERLY" | string;
  category: string;
  subcategory: string;
  is_context_variable: boolean;
  geography: string;
  textile_chain_level: string | null;
  seasonal_adjustment: string;
  price_type: string;
  currency: string | null;
  source_code: string | null;
  source_institution: string | null;
  source_series_code: string;
  source_url: string;
  methodology_url: string | null;
  start_date: string | null;
  end_date: string | null;
  last_observation_date: string | null;
  last_updated_at: string | null;
  last_extracted_at: string | null;
  series_type: "OFFICIAL" | "DERIVED" | string;
  audit_status: "VERIFIED" | "WARNING" | "PENDING" | "REJECTED" | string;
  quality_score: number | null;
  latest: LatestSummary | null;
}

export interface SeriesDetail extends SeriesCard {
  observations_count: number;
  educational: {
    what_it_measures: string;
    how_it_is_built: string;
    economic_relevance: string;
    methodology_summary: string;
    interpretation_notes: string;
    limitations: string;
    economic_sense_note: string;
  };
  dataset: {
    dataset_code: string | null;
    title: string | null;
    official_url: string | null;
  };
  derived_lineage: {
    source_series_ids: string[];
    formula: string;
    deflator_series_code: string | null;
    calculation_version: string;
    calculated_at: string;
    notes: string | null;
  } | null;
  suggested_comparisons: Array<{
    series_code: string;
    short_name: string;
    series_name: string;
    unit: string;
    frequency: string;
    category: string;
    is_context_variable: boolean;
  }>;
  research_questions: string[];
  quality_breakdown: Record<string, { score: number; max: number }> | null;
  audit_findings: Array<{
    check_category: string;
    check_code: string;
    severity: string;
    message: string;
    details: Record<string, unknown> | null;
  }>;
}

export interface ObservationPoint {
  date: string;
  value: number;
  raw_value?: number;
  is_preliminary: boolean;
  is_outlier_flagged: boolean;
  revision_number: number;
}

export interface SeriesObservationsResponse {
  series_code: string;
  series_name: string;
  unit: string;
  frequency: string;
  transform: string;
  meta: {
    transform: string;
    warnings: string[];
    base_date_used?: string;
    base_value_used?: number;
  };
  count: number;
  observations: ObservationPoint[];
  revisions_history: Array<{
    observation_date: string;
    value: number;
    revision_number: number;
    is_current: boolean;
    retrieved_at: string;
  }>;
}

export interface SearchResultItem {
  series_code: string;
  series_name: string;
  short_name: string;
  description: string;
  category: string;
  subcategory: string;
  is_context_variable: boolean;
  source_institution: string | null;
  unit: string;
  frequency: string;
  start_date: string | null;
  last_observation_date: string | null;
  audit_status: string;
  series_type: string;
  quality_score: number | null;
  match_reason: string;
  score: number;
}

export interface CompareResponse {
  mode: string;
  base_date: string | null;
  align_monthly: string | null;
  warnings: Array<{ code: string; severity: string; message: string }>;
  correlation_caution: string;
  series: Array<{
    series_code: string;
    series_name: string;
    short_name: string;
    unit: string;
    frequency: string;
    effective_frequency: string;
    series_type: string;
    is_context_variable: boolean;
    seasonal_adjustment: string;
    price_type: string;
    source_institution: string | null;
    observations: ObservationPoint[];
  }>;
}

export interface TraceabilityResponse {
  series_code: string;
  series_name: string;
  audit_status: string;
  series_type: string;
  steps: Array<{
    step: number;
    stage: string;
    label: string;
    detail: string;
  }>;
  raw_snapshot: {
    raw_id: number | null;
    payload_sha256: string | null;
    extracted_at: string | null;
  };
}

export interface GlossaryItem {
  term_key: string;
  title: string;
  short_explanation: string;
  academic_note: string | null;
}

export interface ResearchSuggestion {
  question: string;
  suggested_topic: string;
  framing_label: string;
  methodological_caution: string;
  primary_variable: {
    series_code: string;
    series_name: string;
    short_name: string;
    unit: string;
    frequency: string;
    category: string;
    is_context_variable: boolean;
    series_type: string;
    start_date: string | null;
    last_observation_date: string | null;
  } | null;
  related_variables: Array<{
    series_code: string;
    series_name: string;
    short_name: string;
    unit: string;
    frequency: string;
    category: string;
    is_context_variable: boolean;
    series_type: string;
    start_date: string | null;
    last_observation_date: string | null;
  }>;
  exploratory_questions: string[];
  structural_preset_id?: string | null;
}

export interface TaxonomyOption {
  code: string;
  label: string;
  description: string;
}

export interface TaxonomyDimension {
  key: "SIZE" | "ORIGIN" | "PRODUCTION_MODEL" | "CHAIN_POSITION";
  letter: string;
  name: string;
  multi_valued: boolean;
  official_criteria: string;
  composite_presets: Array<{ code: string; label: string; includes: string[] }>;
  options: TaxonomyOption[];
}

export interface IndustryTaxonomy {
  module_status: string;
  core_principle: string;
  source_rule: {
    required: string;
    fallback: string;
    forbidden_sources: string[];
  };
  dimensions: TaxonomyDimension[];
}

export interface CompanyClassificationHistoryItem {
  history_id: number;
  company_id: number;
  dimension: "SIZE" | "ORIGIN" | "PRODUCTION_MODEL" | "CHAIN_POSITION" | string;
  classification: string;
  classification_label: string;
  valid_from: string;
  valid_to: string | null;
  official_source_id: number | null;
  official_source_code: string | null;
  official_source_institution: string | null;
  source_url: string | null;
  evidence: string;
  audit_status: "VERIFIED" | "WARNING" | "PENDING" | "REJECTED" | string;
  audit_notes: string | null;
  recorded_at: string | null;
}

export interface CompanyItem {
  company_id: number;
  legal_name: string;
  brand_name: string | null;
  cuit: string | null;
  company_size: string;
  company_size_label: string;
  company_origin: string;
  company_origin_label: string;
  production_model: string;
  production_model_label: string;
  chain_positions: string[];
  chain_position_labels: string[];
  classification_status: string;
  classification_status_label: string;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CompanyDetail extends CompanyItem {
  classification_history: CompanyClassificationHistoryItem[];
}

export interface CompaniesListResponse {
  count: number;
  filters_applied: {
    size: string[];
    origin: string[];
    production_model: string[];
    chain_position: string[];
    chain_match: string;
    classification_status: string | null;
    q: string | null;
  };
  items: CompanyItem[];
}

export interface IndustryStructureSummary {
  module_status: string;
  total_companies: number;
  classification_status_counts: {
    VERIFIED_COMPLETE: number;
    PARTIALLY_VERIFIED: number;
    UNKNOWN: number;
  };
  audit_history_counts: {
    VERIFIED: number;
    REJECTED: number;
    PENDING: number;
    WARNING: number;
  };
  dimensions: {
    SIZE: Array<{ code: string; label: string; count: number }>;
    ORIGIN: Array<{ code: string; label: string; count: number }>;
    PRODUCTION_MODEL: Array<{ code: string; label: string; count: number }>;
    CHAIN_POSITION: Array<{ code: string; label: string; count: number }>;
  };
  approved_official_sources: Array<{
    official_source_id: number;
    source_code: string;
    institution: string;
    official_domain: string;
    notes: string | null;
  }>;
}

export interface StructuralResearchSeriesRef {
  series_code: string;
  series_name: string;
  short_name: string;
  unit: string;
  frequency: string;
  category: string;
  is_context_variable: boolean;
  series_type: string;
  start_date: string | null;
  last_observation_date: string | null;
}

export interface StructuralResearchPreset {
  preset_id: string;
  title: string;
  short_label: string;
  dimensions_involved: string[];
  segment_a: { label: string; filters: Record<string, string[]> };
  segment_b: { label: string; filters: Record<string, string[]> };
  segment_a_company_count: number;
  segment_b_company_count: number;
  recommended_series: string[];
  recommended_series_details: StructuralResearchSeriesRef[];
  exploratory_questions: string[];
  non_causality_warning: string;
}

export interface StructuralResearchFrame {
  mode: "preset" | "custom";
  preset_id: string | null;
  title: string;
  dimensions_involved: string[];
  segment_comparison?: {
    segment_a: { label: string; filters: Record<string, string[]>; verified_company_count: number };
    segment_b: { label: string; filters: Record<string, string[]>; verified_company_count: number };
    companies_with_unknown_status: number;
  };
  segment_profile?: {
    description: string;
    filters: {
      sizes: string[];
      origins: string[];
      production_models: string[];
      chain_positions: string[];
    };
    matching_companies_count: number;
    total_registered_companies: number;
  };
  exploratory_questions: string[];
  recommended_series: StructuralResearchSeriesRef[];
  non_causality_warning: string;
  data_coverage_note: string;
}
