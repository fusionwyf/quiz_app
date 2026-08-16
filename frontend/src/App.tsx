// 路由定义
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './layouts/AppLayout';
import BanksPage from './pages/BanksPage';
import QuestionsPage from './pages/QuestionsPage';
import QuizStartPage from './pages/QuizStartPage';
import QuizPlayPage from './pages/QuizPlayPage';
import MistakesPage from './pages/MistakesPage';
import RecordsPage from './pages/RecordsPage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <ConfigProvider locale={zhCN}>
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
