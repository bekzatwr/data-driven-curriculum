// Типы повторяют contracts/openapi.json ветки integration/p0-server.
// null = «нет допустимого расчёта», его нельзя превращать в 0.

export interface Counts {
  students: number;
  classes: number;
  topics: number;
  textbooks: number;
  results: number;
  pre: number;
  post: number;
  pairs: number;
}

export interface DatasetMetadata {
  name: string;
  subject: string;
  grade: number;
  period_start: string;
  period_end: string;
}

export type SourceType = 'upload' | 'demo';

export interface Dataset {
  id: string;
  metadata: DatasetMetadata;
  source_type: SourceType;
  content_hash: string;
  created_at: string;
  counts: Counts;
}

export interface DatasetList {
  items: Dataset[];
  total: number;
  limit: number;
  offset: number;
}

export interface Capabilities {
  version: string;
  mode: string;
  limits: {
    csv_files_bytes: number;
    multipart_body_bytes: number;
    results_per_dataset: number;
    topics_per_dataset: number;
    [key: string]: number;
  };
  features: Partial<Record<FeatureFlag, boolean>> & Record<string, boolean>;
  links: Record<string, string>;
}

/** Флаги capabilities, от которых зависит интерфейс (источник истины — сервер). */
export type FeatureFlag =
  | 'csv_import'
  | 'import_preview'
  | 'demo_dataset'
  | 'package_export'
  | 'package_restore'
  | 'plan_preview'
  | 'plan_save'
  | 'plan_report'
  | 'plan_csv'
  | 'analytics'
  | 'textbook_comparison'
  | 'comments'
  | 'comments_write'
  | 'ai_explain'
  | 'teachers_api'
  | 'period_planner_api';

export interface ResultRow {
  student_id: string;
  school_id: string;
  class_id: string;
  teacher_id: string;
  textbook_id: string;
  topic_id: string;
  test_version: string;
  stage: string;
  score: number | null;
  max_score: number | null;
  tested_at: string;
}

export interface CurriculumRow {
  topic_id: string;
  topic_name: string;
  topic_order: number;
  current_hours: number;
  min_hours: number;
  max_hours: number;
  importance: number;
  is_locked: boolean;
}

export interface ImportResponse {
  valid: boolean;
  dry_run: boolean;
  created: boolean;
  dataset_id: string | null;
  dataset: Dataset | null;
  metadata: DatasetMetadata;
  counts: Counts;
  preview: { results: ResultRow[]; curriculum: CurriculumRow[] };
  warnings: string[];
}

export interface ClassFilter {
  id: string;
  school_id: string;
  student_count: number;
}

export interface TextbookFilter {
  id: string;
  label: string;
}

export interface TestVersion {
  topic_id: string;
  test_version: string;
  max_score: number;
}

export interface Filters {
  dataset_id: string;
  classes: ClassFilter[];
  textbooks: TextbookFilter[];
  topics: CurriculumRow[];
  test_versions: TestVersion[];
}

export interface Slice {
  test_version: string;
  max_score: number;
}

export type TopicStatus =
  | 'requires_attention'
  | 'needs_practice'
  | 'mastered'
  | 'insufficient_data'
  | 'no_data'
  | 'mixed_versions';

export interface TopicMetrics {
  topic_id: string;
  topic_name: string;
  topic_order: number;
  test_version: string | null;
  max_score: number | null;
  mean_post_pct: number | null;
  below_threshold_share: number | null;
  n_post: number;
  n_pairs: number;
  mean_pre_paired_pct: number | null;
  mean_post_paired_pct: number | null;
  mean_gain_pp: number | null;
  pair_coverage: number | null;
  status: TopicStatus;
  status_label: string;
  problem_topic: boolean | null;
  single_version: boolean;
  available_slices: Slice[];
  warnings: string[];
}

export interface AppliedFilters {
  class_ids: string[];
  textbook_ids: string[];
  test_version: string | null;
}

export interface AnalyticsSettings {
  threshold_pct: number;
  mastered_pct: number;
  min_students: number;
  problem_share: number;
  max_baseline_gap_pp: number;
}

export interface SourceInfo {
  id: string;
  metadata: DatasetMetadata;
  counts: Counts;
  content_hash: string;
  source_type: SourceType;
  created_at: string;
}

export interface OverviewMetrics {
  n_students: number;
  n_post_students: number;
  n_post_results: number;
  n_pairs: number;
  n_paired_students: number;
  pair_coverage: number | null;
  paired_student_share: number | null;
  mean_post_pct: number | null;
  n_complete_students: number;
  topic_count: number;
  n_problem_topics: number;
  mixed_topic_ids: string[];
  warnings: string[];
}

export interface ClassMetrics {
  school_id: string;
  class_id: string;
  metrics: TopicMetrics;
}

export interface Overview {
  dataset_id: string;
  is_demo: boolean;
  source: SourceInfo;
  applied_filters: AppliedFilters;
  settings: AnalyticsSettings;
  warnings: string[];
  metrics: OverviewMetrics;
  topics: TopicMetrics[];
  heatmap: ClassMetrics[];
}

export interface TopicDetail {
  dataset_id: string;
  is_demo: boolean;
  applied_filters: AppliedFilters;
  settings: AnalyticsSettings;
  warnings: string[];
  metrics: TopicMetrics;
  by_class: ClassMetrics[];
  slices: TopicMetrics[];
}

export type ComparisonStatus = 'comparable' | 'insufficient_data' | 'not_comparable';

export interface BookGroup {
  textbook_id: string;
  n_post: number;
  n_pairs: number;
  n_classes: number;
  n_teachers: number;
  pair_coverage: number | null;
  mean_post_pct: number | null;
  mean_pre_paired_pct: number | null;
  mean_post_paired_pct: number | null;
  mean_gain_pp: number | null;
  available_slices: Slice[];
}

export interface Comparison {
  dataset_id: string;
  is_demo: boolean;
  source: SourceInfo;
  applied_filters: AppliedFilters;
  settings: AnalyticsSettings;
  warnings: string[];
  topic_id: string;
  test_version: string | null;
  max_score: number | null;
  comparison_status: ComparisonStatus;
  difference_gain_pp: number | null;
  baseline_gap_pp: number | null;
  group_a: BookGroup;
  group_b: BookGroup;
  reasons: string[];
  conclusion: string;
}

// ---------- Планировщик ----------

export interface PlanSettings {
  target_pct: number;
  donor_pct: number;
  min_students: number;
  max_change: number;
}

export interface ConstraintOverride {
  min_hours?: number | null;
  max_hours?: number | null;
  importance?: number | null;
  is_locked?: boolean | null;
}

export interface PlanRequest {
  class_id: string;
  test_versions?: Record<string, string>;
  constraints?: Record<string, ConstraintOverride>;
  settings?: PlanSettings;
}

export interface SaveRequest extends PlanRequest {
  hours_by_topic?: Record<string, number> | null;
  comment?: string;
}

export interface PlanItem {
  topic_id: string;
  topic_name: string;
  topic_order: number;
  current_hours: number;
  min_hours: number;
  max_hours: number;
  importance: number;
  is_locked: boolean;
  mean_post_pct: number | null;
  n_post: number;
  test_version: string | null;
  max_score: number | null;
  automatic_eligible: boolean;
  proposed_hours: number;
  delta: number;
  reason: string;
}

export interface Transfer {
  from_topic_id: string;
  to_topic_id: string;
  hours: number;
}

export interface PlanMetric {
  topic_id: string;
  mean_post_pct: number | null;
  n_post: number;
  single_version: boolean;
  test_version: string | null;
  max_score: number | null;
}

export interface PlanSource {
  id: string;
  source_type: SourceType;
  metadata: DatasetMetadata;
  counts: Counts;
  content_hash: string;
  created_at: string;
}

export interface PlanPreview {
  total_hours: number;
  dataset_id: string;
  class_id: string;
  applied_filters: { class_ids: string[]; test_versions: Record<string, string> };
  source: PlanSource;
  is_demo: boolean;
  metrics: PlanMetric[];
  warnings: string[];
  settings: PlanSettings;
  algorithm_version: string;
  items: PlanItem[];
  transfers: Transfer[];
}

export interface SavedItem extends PlanItem {
  recommended_hours: number;
  recommendation_reason: string;
  manually_modified: boolean;
}

export interface SavedPlan extends Omit<PlanPreview, 'items' | 'transfers'> {
  plan_id: string;
  created_at: string;
  items: SavedItem[];
  manually_modified: boolean;
  comment: string;
  recommendation_transfers: Transfer[];
}

export interface ErrorDetail {
  file?: string | null;
  row?: number | null;
  field?: string | null;
  reason?: string;
  [key: string]: unknown;
}

export interface ErrorBody {
  code: string;
  message: string;
  details?: ErrorDetail[];
  total_errors?: number;
}

// ---------- P1: комментарии и ИИ (модуль collab) ----------

export type CommentTarget = 'dataset' | 'topic' | 'textbook' | 'class' | 'teacher' | 'plan' | 'plan_topic';
export type AuthorRole = 'teacher' | 'methodist' | 'admin' | 'ai';

export interface CommentItem {
  id: string;
  dataset_id: string;
  target_type: CommentTarget;
  target_id: string;
  author_name: string;
  author_school: string;
  author_role: AuthorRole;
  kind: 'human' | 'ai';
  text: string;
  created_at: string;
}

export interface CommentList {
  items: CommentItem[];
  total: number;
}

/**
 * Виды ИИ-пояснений, которые сервер (PR #6) реально обслуживает.
 * teachers/comments сервер отвечает 503 AI_KIND_NOT_READY — во фронтенде не используются.
 */
export type AiKind = 'overview' | 'topic' | 'comparison' | 'plan';

/** Только селекторы: показатели сервер считает сам, браузер не передаёт данные и тексты. */
export interface AiSelectors {
  class_ids?: string[];
  textbook_ids?: string[];
  test_version?: string | null;
  topic_id?: string;
  textbook_a?: string;
  textbook_b?: string;
  plan_id?: string;
}

/** Роль автора, которую может отправить человек (ai сервер не принимает). */
export type HumanRole = Exclude<AuthorRole, 'ai'>;

export interface Explanation {
  text: string;
  provider: string;
  model: string;
  created_at: string;
}

export interface RecordsPage {
  dataset_id: string;
  items: ResultRow[];
  total: number;
  limit: number;
  offset: number;
}
