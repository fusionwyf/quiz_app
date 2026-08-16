// LLM 智能整理配置表单：设置页与导入弹窗共用
import { useEffect, useState } from 'react';
import { Button, Form, Input, Select, Space, message } from 'antd';
import { getLlmConfig, testLlmConfig, updateLlmConfig } from '../api';

interface FormValues {
  provider: string;
  base_url?: string;
  model?: string;
  api_key?: string;
}

interface LlmSettingsFormProps {
  /** 保存成功后回调（如刷新状态提示、关闭容器） */
  onSaved?: (config: { enabled: boolean; model: string }) => void;
}

export default function LlmSettingsForm({ onSaved }: LlmSettingsFormProps) {
  const [form] = Form.useForm<FormValues>();
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [keySet, setKeySet] = useState(false);
  const [keyMasked, setKeyMasked] = useState('');

  const provider = Form.useWatch('provider', form) ?? 'none';

  useEffect(() => {
    let cancelled = false;
    getLlmConfig()
      .then((cfg) => {
        if (cancelled) return;
        form.setFieldsValue({
          // local（进程内 GGUF）仅支持环境变量配置，界面不提供该选项
          provider: cfg.provider === 'local' ? 'none' : cfg.provider,
          base_url: cfg.base_url,
          model: cfg.model,
        });
        setKeySet(cfg.api_key_set);
        setKeyMasked(cfg.api_key_masked);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [form]);

  const buildPayload = (values: FormValues) => ({
    provider: values.provider,
    // 空 base_url/model 清除覆盖（回退环境变量/默认值），空 api_key 保留已存 Key
    base_url: (values.base_url ?? '').trim(),
    model: (values.model ?? '').trim(),
    api_key: (values.api_key ?? '').trim(),
  });

  const handleTest = async () => {
    const values = await form.validateFields();
    setTesting(true);
    try {
      const res = await testLlmConfig(buildPayload(values));
      message.success(
        `连接成功（${res.model} 回复：${(res.reply || 'OK').slice(0, 30)}）`,
      );
    } catch {
      // 失败原因由 axios 拦截器统一弹出
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const cfg = await updateLlmConfig(buildPayload(values));
      setKeySet(cfg.api_key_set);
      setKeyMasked(cfg.api_key_masked);
      message.success(
        cfg.enabled
          ? `已启用 AI 智能整理（${cfg.model}）`
          : '已保存（AI 智能整理未启用）',
      );
      onSaved?.(cfg);
    } catch {
      // 拦截器已提示
    } finally {
      setSaving(false);
    }
  };

  return (
    <Form form={form} layout="vertical" disabled={loading}>
      <Form.Item
        name="provider"
        label="API 类型"
        rules={[{ required: true }]}
        initialValue="none"
      >
        <Select
          options={[
            { value: 'none', label: '禁用（不使用 AI 整理）' },
            {
              value: 'openai',
              label: 'OpenAI 兼容 API（OpenAI / DeepSeek / Ollama 等）',
            },
          ]}
        />
      </Form.Item>
      {provider === 'openai' && (
        <>
          <Form.Item
            name="base_url"
            label="Base URL"
            extra="OpenAI 兼容端点地址；本地 Ollama 填 http://localhost:11434/v1（留空使用默认值）"
            rules={[
              {
                pattern: /^https?:\/\//,
                message: '必须以 http:// 或 https:// 开头',
              },
            ]}
          >
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名"
            rules={[{ required: true, message: '请填写模型名' }]}
          >
            <Input placeholder="gpt-4o-mini / deepseek-chat / qwen2.5:3b" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API Key"
            extra={
              keySet
                ? `已配置（${keyMasked}），留空表示保留原有 Key`
                : 'Ollama 等本地服务通常无需填写'
            }
          >
            <Input.Password
              placeholder={keySet ? keyMasked : 'sk-...'}
              autoComplete="new-password"
            />
          </Form.Item>
        </>
      )}
      <Space>
        <Button onClick={handleTest} loading={testing} disabled={provider !== 'openai'}>
          测试连接
        </Button>
        <Button type="primary" onClick={handleSave} loading={saving}>
          保存配置
        </Button>
      </Space>
    </Form>
  );
}
