// TypeScript interfaces for all 4 data schemas.
// These match exactly what step5_generate_frontend_json() writes to data/.

// ── Policy record ─────────────────────────────────────────────────────────────
export interface PolicyRecord {
  title: string;
  link: string;
  pub_date: string;           // "YYYY-MM-DD"
  department: string;
  policy_type: string | null;
  cwrq: string | null;        // 成文日期 (for 国务院 records)
  fwzh: string | null;        // 文号 e.g. "国办发〔2010〕4号"
  source_col: string | null;  // NHSA column: col104/col147/col105/col14
  tags_display: string | null;
  tag_集采: boolean;
  tag_医保: boolean;
  tag_创新药: boolean;
  tag_医改: boolean;
  tag_临床试验: boolean;
  tag_药监: boolean;
  tag_疫苗: boolean;
}

// ── News record ───────────────────────────────────────────────────────────────
export interface NewsRecord {
  date: string;       // "YYYY-MM-DD"
  title: string;
  tags: string[];
  summary: string;
}

// ── Drug pipeline record ──────────────────────────────────────────────────────
export type DrugPhase =
  | '临床I期'
  | '临床II期'
  | '临床III期'
  | 'NDA申请'
  | '已上市';

export interface DrugRecord {
  drug_name: string;
  institution: string;
  target: string;
  current_phase: DrugPhase;
  event_date: string;   // "YYYY-MM-DD"
  source_url: string;
  notes: string | null;
}

// ── Academic paper record ─────────────────────────────────────────────────────
export interface AcademicRecord {
  title: string;
  authors: string;
  journal: string;
  abstract: string;
  url: string;
  pub_date: string;   // "YYYY-MM"
  keywords: string[];
}

// ── Route params ──────────────────────────────────────────────────────────────
export type Industry = 'biomedicine' | 'biomanufacturing';
export type Country = 'china';
export type Module =
  | 'policy_all'
  | 'policy_monthly'
  | 'news_monthly'
  | 'drugs_monthly'
  | 'academic_monthly';

export interface RouteParams {
  industry: string;
  country: string;
  module: string;
}
