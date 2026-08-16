// 分模块的 API 函数：页面统一从这里调用，不直接使用 axios
import { API_BASE, client } from './client';
import type {
  AnswerSubmission,
  CheckResult,
  CreateQuestionDTO,
  ExportResult,
  ImportResult,
  LlmConfig,
  LlmConfigInput,
  LlmStatus,
  LlmTestResult,
  MistakeItem,
  PaginatedRecords,
  Question,
  QuestionBank,
  QuestionDTO,
  QuestionListResult,
  QuestionStats,
  AutoBackupItem,
  RestoreResult,
  QuizSession,
  SessionStatus,
  SessionSummary,
  UpdateQuestionDTO,
} from './types';

// ===== 题库管理 =====

export async function listBanks(signal?: AbortSignal): Promise<QuestionBank[]> {
  const { data } = await client.get<QuestionBank[]>('/banks', { signal });
  return data;
}

export async function createBank(name: string): Promise<QuestionBank> {
  const { data } = await client.post<QuestionBank>('/banks/create', null, {
    params: { name },
  });
  return data;
}

/** 删除题库（后端级联删除题目、错题与答题记录） */
export async function deleteBank(bankId: number): Promise<void> {
  await client.delete(`/banks/${bankId}`);
}

// ===== 导入 / 导出 =====

export async function importQuestionsFile(
  bankId: number,
  file: File,
  forceLlm = false,
): Promise<ImportResult> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await client.post<ImportResult>(
    `/banks/${bankId}/import/file`,
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: forceLlm ? { force_llm: true } : undefined,
      // AI 强制整理长文本分块调用耗时较长
      timeout: 0,
    },
  );
  return data;
}

/** 题库题目分页列表（题目管理页数据源；空题库返回 total=0，失败不弹提示） */
export async function listQuestions(
  bankId: number,
  page = 1,
  pageSize = 20,
): Promise<QuestionListResult> {
  const { data } = await client.get<QuestionListResult>(
    `/banks/${bankId}/questions`,
    { params: { page, page_size: pageSize }, silent: true },
  );
  return data;
}

/** 导出题库（返回完整题目数组；silent 时失败不弹提示） */
export async function exportQuestions(
  bankId: number,
  options?: { silent?: boolean; signal?: AbortSignal },
): Promise<ExportResult> {
  const { data } = await client.get<ExportResult>(`/banks/${bankId}/export`, {
    params: { format: 'json' },
    silent: options?.silent,
    signal: options?.signal,
  });
  return data;
}

/** 导出下载链接（json / txt） */
export function exportUrl(bankId: number, format: 'json' | 'txt'): string {
  return `${API_BASE}/banks/${bankId}/export?format=${format}`;
}

// ===== LLM 智能整理 =====

export async function getLlmStatus(): Promise<LlmStatus> {
  const { data } = await client.get<LlmStatus>('/llm/status', {
    silent: true,
  });
  return data;
}

/** 查询生效配置（数据库覆盖 > 环境变量），API Key 脱敏 */
export async function getLlmConfig(): Promise<LlmConfig> {
  const { data } = await client.get<LlmConfig>('/llm/config');
  return data;
}

/** 保存配置到数据库；空 base_url/model 清除覆盖，空 api_key 保留已存 Key */
export async function updateLlmConfig(
  payload: LlmConfigInput,
): Promise<LlmConfig> {
  const { data } = await client.put<LlmConfig>('/llm/config', payload);
  return data;
}

/** 测试连通性：带 payload 先测后存，不带测已保存配置（失败由拦截器提示） */
export async function testLlmConfig(
  payload?: LlmConfigInput,
): Promise<LlmTestResult> {
  const { data } = await client.post<LlmTestResult>(
    '/llm/test',
    payload ?? null,
    { timeout: 0 },
  );
  return data;
}

// ===== 题目 CRUD =====

export async function createQuestion(
  dto: CreateQuestionDTO,
): Promise<QuestionDTO> {
  const { data } = await client.post<QuestionDTO>('/questions', dto);
  return data;
}

export async function getQuestion(id: number): Promise<QuestionDTO> {
  const { data } = await client.get<QuestionDTO>(`/questions/${id}`);
  return data;
}

export async function updateQuestion(
  id: number,
  dto: UpdateQuestionDTO,
): Promise<QuestionDTO> {
  const { data } = await client.put<QuestionDTO>(`/questions/${id}`, dto);
  return data;
}

export async function deleteQuestion(id: number): Promise<void> {
  await client.delete(`/questions/${id}`);
}

// ===== 做题 Session =====

export async function startSession(
  bankId: number,
  mode: 'sequential' | 'random',
  source: 'normal' | 'mistake' = 'normal',
): Promise<QuizSession> {
  const { data } = await client.post<QuizSession>('/session/start', null, {
    params: { bank_id: bankId, mode, source },
  });
  return data;
}

export async function getCurrentQuestion(
  sessionId: number,
): Promise<QuestionDTO> {
  const { data } = await client.get<QuestionDTO>(
    `/session/${sessionId}/current`,
  );
  return data;
}

export async function submitAnswer(
  sessionId: number,
  submission: AnswerSubmission,
): Promise<CheckResult> {
  const { data } = await client.post<CheckResult>(
    `/session/${sessionId}/answer`,
    submission,
  );
  return data;
}

export async function getSessionStatus(
  sessionId: number,
): Promise<SessionStatus> {
  const { data } = await client.get<SessionStatus>(
    `/session/${sessionId}/status`,
  );
  return data;
}

export async function finishSession(
  sessionId: number,
): Promise<SessionSummary> {
  const { data } = await client.post<SessionSummary>(
    `/session/${sessionId}/finish`,
  );
  return data;
}

// ===== 错题本 =====

export async function getMistakeBook(
  bankId?: number,
  signal?: AbortSignal,
): Promise<MistakeItem[]> {
  const { data } = await client.get<{ mistakes: MistakeItem[] }>('/mistakes', {
    params: bankId !== undefined ? { bank_id: bankId } : undefined,
    signal,
  });
  return data.mistakes;
}

// 手动已掌握：移出错题本（错题由答错自动记录，无需手动加入）
export async function markMastered(questionId: number): Promise<void> {
  await client.delete(`/mistakes/${questionId}`);
}

// ===== 连对出本阈值 =====

export async function getMasterThreshold(): Promise<number> {
  const { data } = await client.get<{ threshold: number }>(
    '/mistakes/master-threshold',
  );
  return data.threshold;
}

export async function setMasterThreshold(value: number): Promise<number> {
  const { data } = await client.put<{ threshold: number }>(
    '/mistakes/master-threshold',
    { value },
  );
  return data.threshold;
}

// ===== 备份/恢复 =====

/** 全库备份 payload（直接落盘为文件） */
export async function createBackup(): Promise<Record<string, unknown>> {
  const { data } = await client.post('/backup');
  return data;
}

export async function listAutoBackups(): Promise<AutoBackupItem[]> {
  const { data } = await client.get<{ backups: AutoBackupItem[] }>(
    '/backup/list',
  );
  return data.backups;
}

/** 从上传的备份 JSON 恢复（覆盖现有全部数据，调用前必须用户确认） */
export async function restoreBackup(
  payload: Record<string, unknown>,
): Promise<RestoreResult> {
  const { data } = await client.post('/backup/restore', payload);
  return data;
}

export async function restoreAutoBackup(
  filename: string,
): Promise<RestoreResult> {
  const { data } = await client.post(`/backup/restore/auto/${filename}`);
  return data;
}

// ===== 答题记录与统计 =====

export interface RecordsQuery {
  page?: number;
  page_size?: number;
  question_id?: number;
  session_id?: number;
  is_correct?: boolean;
}

export async function getRecords(
  query: RecordsQuery,
  signal?: AbortSignal,
): Promise<PaginatedRecords> {
  const { data } = await client.get<PaginatedRecords>('/records', {
    params: query,
    signal,
  });
  return data;
}

export async function getQuestionStats(
  questionId: number,
): Promise<QuestionStats> {
  const { data } = await client.get<QuestionStats>(
    `/stats/questions/${questionId}`,
  );
  return data;
}

export type { Question };
