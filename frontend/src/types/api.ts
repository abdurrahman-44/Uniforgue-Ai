export interface UserProfile {
  full_name: string;
  university: string | null;
  department: string | null;
  academic_level: string;
  bio: string | null;
  country: string | null;
  avatar_asset_id: string | null;
}

export interface UserSettings {
  theme: "dark" | "light" | "system";
  language: string;
  reduced_motion: boolean;
  default_citation_style: string;
  ai_context_opt_in: boolean;
  storage_quota_bytes: number;
}

export interface User {
  id: string;
  email: string;
  role: "student" | "moderator" | "admin";
  is_verified: boolean;
  is_active: boolean;
  created_at: string | null;
  profile: UserProfile;
  settings: UserSettings;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  visibility?: string;
  is_personal: boolean;
  owner_id?: string;
}

export interface AcademicProject {
  id: string;
  workspace_id: string;
  title: string;
  course_code: string | null;
  subject: string | null;
  description: string | null;
  project_type: string;
  status: string;
  citation_style: string;
  due_date: string | null;
  notes?: string;
  updated_at: string;
}

export interface DocumentItem {
  id: string;
  project_id: string | null;
  title: string;
  doc_type: string;
  citation_style: string;
  content_markdown?: string;
  content_html?: string;
  word_count: number;
  version_number: number;
  cover_page?: Record<string, unknown>;
  formatting_profile?: Record<string, unknown>;
  assignment_requirements?: AssignmentAnalysis | null;
  updated_at: string;
}

export interface AssignmentAnalysis {
  questions: string[];
  required_sections: string[];
  formatting_rules: string[];
  word_limits: { min: number | null; max: number | null; current_draft_words: number };
  submission_requirements: string[];
  assessment_criteria: string[];
  checklist: { item: string; category: string; status: string }[];
  missing_requirements: string[];
  improvement_suggestions: string[];
  coverage_percent: number;
  disclaimer: string;
}

export interface ResearchSource {
  id?: string;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  doi: string | null;
  url: string | null;
  abstract: string | null;
  source_provider: string;
  external_id?: string | null;
  provenance_status: "discovered" | "retrieved" | "verified";
  citation_count: number | null;
  notes?: string;
}

export interface DiagramItem {
  id: string;
  project_id: string | null;
  title: string;
  diagram_type: string;
  engine: string;
  nodes_json?: Array<{
    id: string;
    type?: string;
    position: { x: number; y: number };
    data: { label: string; color?: string; shape?: string };
  }>;
  edges_json?: Array<{
    id: string;
    source: string;
    target: string;
    label?: string;
  }>;
  mermaid_code?: string;
  plantuml_code?: string;
  node_count?: number;
  edge_count?: number;
  updated_at: string;
}

export interface PresentationSlide {
  id: string;
  order_index: number;
  layout: string;
  title: string;
  bullets: string[];
  body_text: string;
  speaker_notes: string;
  image_asset_id?: string | null;
  chart_data?: Record<string, unknown> | null;
}

export interface PresentationItem {
  id: string;
  project_id: string | null;
  title: string;
  subtitle: string | null;
  theme: string;
  aspect_ratio: string;
  slides?: PresentationSlide[];
  updated_at?: string;
}

export interface MediaAssetItem {
  id: string;
  filename: string;
  original_filename?: string;
  mime_type: string;
  asset_type?: string;
  size_bytes: number;
  download_url: string;
  has_extracted_text?: boolean;
  extracted_preview?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface NotificationItem {
  id: string;
  category: string;
  title: string;
  message: string;
  action_url: string | null;
  is_read: boolean;
  created_at: string;
}

export interface TaskItem {
  id: string;
  project_id: string | null;
  title: string;
  description?: string | null;
  status: "todo" | "in_progress" | "done";
  priority: "low" | "medium" | "high" | "urgent";
  progress_percent: number;
  due_date: string | null;
}
