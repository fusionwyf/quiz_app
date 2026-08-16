// 全站共享的查询键与数据 hooks（TanStack Query）。
// 页面取数统一从这里走；失效策略：写操作后 invalidate 对应键。
import { useQuery } from '@tanstack/react-query';
import { getMistakeBook, getRecords, listBanks } from './index';

export const queryKeys = {
  banks: ['banks'] as const,
  questions: (bankId: number, page: number, pageSize: number) =>
    ['questions', bankId, page, pageSize] as const,
  mistakes: (bankId?: number) => ['mistakes', bankId ?? 'all'] as const,
  records: (params: { page: number; page_size: number; is_correct?: boolean }) =>
    ['records', params] as const,
  llmStatus: ['llm-status'] as const,
  autoBackups: ['auto-backups'] as const,
};

/** 题库列表（多处共用：题库页、做题入口、错题筛选） */
export function useBanks() {
  return useQuery({
    queryKey: queryKeys.banks,
    queryFn: ({ signal }) => listBanks(signal),
  });
}

/** 错题本列表（bankId 缺省 = 全部题库） */
export function useMistakeBook(bankId?: number) {
  return useQuery({
    queryKey: queryKeys.mistakes(bankId),
    queryFn: ({ signal }) => getMistakeBook(bankId, signal),
  });
}

/** 错题总数（侧边栏角标；与错题本共享缓存，答错后经 invalidate 自动更新） */
export function useMistakeCount() {
  const { data } = useMistakeBook();
  return data?.length ?? 0;
}

/** 答题记录分页 */
export function useRecords(params: {
  page: number;
  page_size: number;
  is_correct?: boolean;
}) {
  return useQuery({
    queryKey: queryKeys.records(params),
    queryFn: ({ signal }) => getRecords(params, signal),
  });
}
