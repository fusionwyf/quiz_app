// 系统设置页：LLM 智能整理 API 配置
import { Card, Typography } from 'antd';
import LlmSettingsForm from '../components/LlmSettingsForm';

const { Paragraph } = Typography;

export default function SettingsPage() {
  return (
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
  );
}
