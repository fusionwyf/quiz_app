// 系统设置页：数据备份 + 错题连对出本阈值 + LLM 智能整理 API 配置
import { Card, Typography } from 'antd';
import BackupCard from '../components/BackupCard';
import LlmSettingsForm from '../components/LlmSettingsForm';
import MistakeThresholdForm from '../components/MistakeThresholdForm';

const { Paragraph } = Typography;

export default function SettingsPage() {
  return (
    <>
      <Card title="数据备份" style={{ maxWidth: 680, marginBottom: 16 }}>
        <Paragraph type="secondary">
          一键把全部数据备份为单个文件（换电脑/重装时带走），或从备份文件恢复；
          每日首次启动会自动在本地留一份备份，滚动保留最近 7 份。
        </Paragraph>
        <BackupCard />
      </Card>
      <Card title="错题练习" style={{ maxWidth: 680, marginBottom: 16 }}>
        <Paragraph type="secondary">
          答错的题会自动加入错题本；重做连续答对达到设定次数后自动移出（已掌握），
          也可以在错题本中手动标记已掌握。
        </Paragraph>
        <MistakeThresholdForm />
      </Card>
      <Card title="AI 智能整理" style={{ maxWidth: 680 }}>
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
    </>
  );
}
