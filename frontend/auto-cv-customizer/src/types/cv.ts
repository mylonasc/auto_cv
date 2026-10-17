/** Canonical CV schema v1. Candidate is identity/profile, never duplicate content. */
export interface CVData {
  schema_version: 1;
  candidate: CandidateMeta;
  cv_template: CVTemplateMeta;
  motivation_letter_template: MotivationLetterTemplateMeta;
  personal_statement: string;
  alternative_statements: string[];
  experience_sections: ExperienceSection[];
}

export interface CandidateMeta {
  candidate_id: string;
  full_name: string;
  profile: Record<string, unknown>;
}

export interface CVTemplateMeta {
  template_id: string;
  template_path: string | null;
  experience_section_title: string;
}

export interface MotivationLetterTemplateMeta {
  template_id: string;
  template_path: string | null;
}

export interface ExperienceSection {
  company: string;
  duration: string;
  position: string;
  text_items: string[];
}
