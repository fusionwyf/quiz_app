// 路由定义 + 主题算法（浅色/深色/跟随系统，经 AppSetting 持久化）
import { useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ConfigProvider, theme as antdTheme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { useQuery } from '@tanstack/react-query';
import AppLayout from './layouts/AppLayout';
import BanksPage from './pages/BanksPage';
import QuestionsPage from './pages/QuestionsPage';
import QuizStartPage from './pages/QuizStartPage';
import QuizPlayPage from './pages/QuizPlayPage';
import MistakesPage from './pages/MistakesPage';
import RecordsPage from './pages/RecordsPage';
import SettingsPage from './pages/SettingsPage';
import { getThemeSetting } from './api';
import { queryKeys } from './api/queries';

type ThemeMode = 'light' | 'dark' | 'system';

function useSystemPrefersDark(): boolean {
  const [dark, setDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  );
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);
  return dark;
}

export default function App() {
  const { data: themeMode = 'system' } = useQuery({
    queryKey: queryKeys.theme,
    queryFn: getThemeSetting,
    staleTime: Infinity, // 只被设置页的保存动作失效
  });
  const systemDark = useSystemPrefersDark();
  const isDark =
    themeMode === 'dark' || (themeMode === 'system' && systemDark);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{ algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm }}
    >
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<BanksPage />} />
            <Route path="/banks/:bankId/questions" element={<QuestionsPage />} />
            <Route path="/quiz/start" element={<QuizStartPage />} />
            <Route path="/quiz/session/:sessionId" element={<QuizPlayPage />} />
            <Route path="/mistakes" element={<MistakesPage />} />
            <Route path="/records" element={<RecordsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export { useSystemPrefersDark };
export type { ThemeMode };
