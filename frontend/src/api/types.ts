// 与后端 DTO / 数据模型对齐的类型定义（api/api.py、api/models.py）

export type QuestionType = 'single' | 'multi' | 'judge' | 'blank';

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  single: '单选题',
  multi: '多选题',
  judge: '判断题',
  blank: '填空题',
};

// ===== 题库 =====

export interface QuestionBank {
  id: number;
  name: string;
  source?: string | null;
  created_at: string;
}

// ===== 题目 =====

/** GET /quiz/random、GET /session/{id}/current 返回的题目视图（不含答案） */
export interface QuestionDTO {
  id: number;
  type: QuestionType;
  question: string;
  options?: Record<string, string> | null;
  score: number;
}

/** GET /banks/{id}/export?format=json 返回的完整题目（含答案） */
export interface Question {
  id: number;
  bank_id: number;
  type: QuestionType;
  content: string;
  options?: Record<string, string> | null;
  answer?: string[] | null;
  blank_answer?: string[] | null;
  score: number;
  created_at?: string | null;
}

export interface ExportResult {
  bank_id: number;
  bank_name: string;
  question_count: number;
  questions: Question[];
}

export interface CreateQuestionDTO {
  bank_id: number;
  type: QuestionType;
  content: string;
  options?: Record<string, string> | null;
  answer?: string[] | null;
  blank_answer?: string[] | null;
  score?: number;
}

export type UpdateQuestionDTO = Partial<Omit<CreateQuestionDTO, 'bank_id'>>;

// ===== 做题 Session =====

export interface QuizSession {
  id: number;
  bank_id: number;
  mode: string;
  question_ids: number[];
  current_index: number;
  total: number;
  created_at: string;
  finished: boolean;
  finished_at?: string | null;
}

export interface AnswerSubmission {
  question_id: number;
  user_choices: string[];
}

export interface CheckResult {
  question_id: number;
  is_correct: boolean;
  correct_answer: string[];
  score_obtained: number;
}

export interface SessionStatus {
  session_id: number;
  bank_id: number;
  mode: string;
  current_index: number;
  total: number;
  finished: boolean;
  progress_percentage: number;
  correct_count: number;
  total_score: number;
  average_score: number;
}

export interface SessionSummary {
  session_id: number;
  bank_id: number;
  mode: string;
  total_questions: number;
  answered_questions: number;
  correct_count: number;
  total_score_obtained: number;
  max_possible_score: number;
  accuracy_percentage: number;
  finished_at?: string | null;
}

// ===== 导入 =====

export interface ImportResult {
  message: string;
  imported_count: number;
  skipped_count: number;
  errors: string[];
  truncated: boolean;
  /** 是否经过 LLM 智能整理兜底 */
  ai_normalized?: boolean;
}

// ===== LLM 智能整理 =====

export interface LlmStatus {
  provider: string;
  enabled: boolean;
  model: string;
}

// ===== 错题本 =====

export interface MistakeItem {
  mistake_id: number;
  question_id: number;
  question_content: string;
  question_type: QuestionType;
  wrong_count: number;
  last_wrong_at: string;
  bank_id: number;
}

// ===== 答题记录与统计 =====

export interface ExamRecordItem {
  id: number;
  session_id?: number | null;
  question_id: number;
  user_answer: string[];
  is_correct: boolean;
  created_at: string;
  question_content?: string | null;
  question_type?: QuestionType | null;
}

export interface PaginatedRecords {
  total: number;
  page: number;
  page_size: number;
  records: ExamRecordItem[];
}

export interface QuestionStats {
  question_id: number;
  question_content: string;
  total_attempts: number;
  correct_attempts: number;
  wrong_attempts: number;
  correct_rate: number;
  average_score: number;
  total_score_obtained: number;
  total_possible_score: number;
}
