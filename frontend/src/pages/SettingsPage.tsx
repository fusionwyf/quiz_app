// 系统设置页：居中响应式网格布局
// 外观 / 错题练习 / 数据备份 / 诊断 / 软件更新 / 关于 两列排布，AI 智能整理占整行
import { Card, Col, Row, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import AboutCard from '../components/AboutCard';
import BackupCard from '../components/BackupCard';
import DiagnosticsCard from '../components/DiagnosticsCard';
import LlmSettingsForm from '../components/LlmSettingsForm';
import MistakeThresholdForm from '../components/MistakeThresholdForm';
import ThemeForm from '../components/ThemeForm';
import UpdateCard from '../components/UpdateCard';
import { getThemeSetting } from '../api';
import { queryKeys } from '../api/queries';

const { Paragraph } = Typography;

export default function SettingsPage() {
  const { data: theme = 'system' } = useQuery({
    queryKey: queryKeys.theme,
    queryFn: getThemeSetting,
    staleTime: Infinity,
  });

  return (
    <div style={{ maxWidth: 1120, margin: '0 auto' }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="外观" style={{ height: '100%' }}>
            <ThemeForm current={theme} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="错题练习" style={{ height: '100%' }}>
            <Paragraph type="secondary">
              答错的题自动加入错题本；重做连续答对达到设定次数后自动移出（已掌握）。
            </Paragraph>
            <MistakeThresholdForm />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="数据备份" style={{ height: '100%' }}>
            <Paragraph type="secondary">
              一键把全部数据备份为单个文件，或从备份恢复；每日首次启动自动留一份，滚动保留
              7 份。
            </Paragraph>
            <BackupCard />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="诊断" style={{ height: '100%' }}>
            <Paragraph type="secondary">
              后端与桌面壳的运行日志保存在本机（滚动清理），不上传。
            </Paragraph>
            <DiagnosticsCard />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="软件更新" style={{ height: '100%' }}>
            <UpdateCard />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="关于" style={{ height: '100%' }}>
            <AboutCard />
          </Card>
        </Col>
        <Col span={24}>
          <Card title="AI 智能整理">
            <Paragraph type="secondary">
              配置 OpenAI 兼容 API 后，导入题库文件时可用 AI
              把格式混乱的原文整理成标准格式再解析：解析出 0 题时自动兜底，也可在导入时勾选
              「强制 AI 整理」全部重新整理；长文件自动分块处理，不会截断丢题。
            </Paragraph>
            <Paragraph type="secondary">
              配置保存在本地数据库（优先级高于 LLM_PROVIDER 等环境变量）；API Key
              明文存储在本地，仅用于调用你配置的 API，不会上传到其他服务。
            </Paragraph>
            <LlmSettingsForm />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
