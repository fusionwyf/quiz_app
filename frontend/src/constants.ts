// 全站共享 UI 常量（收敛各页重复定义）
import type { QuestionType } from './api/types';

/** 题型标签色（原各页重复定义，现唯一来源） */
export const TYPE_COLORS: Record<QuestionType, string> = {
  single: 'blue',
  multi: 'purple',
  judge: 'cyan',
  blank: 'orange',
};
