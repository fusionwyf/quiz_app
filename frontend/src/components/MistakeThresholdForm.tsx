// 错题连对出本阈值设置表单
import { useEffect, useState } from 'react';
import { Button, InputNumber, Space, Typography, message } from 'antd';
import { getMasterThreshold, setMasterThreshold } from '../api';

export default function MistakeThresholdForm() {
  const [threshold, setThreshold] = useState<number>(2);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const value = await getMasterThreshold();
        if (!cancelled) setThreshold(value);
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSave = async () => {
    if (threshold < 1) {
      message.warning('阈值必须 >= 1');
      return;
    }
    setSaving(true);
    try {
      const saved = await setMasterThreshold(threshold);
      setThreshold(saved);
      message.success('已保存');
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  };

  return (
    <Space wrap>
      <Typography.Text>连续答对</Typography.Text>
      <InputNumber
        min={1}
        max={10}
        value={threshold}
        disabled={loading}
        onChange={(v) => setThreshold(v ?? 2)}
      />
      <Typography.Text>次后自动移出错题本</Typography.Text>
      <Button type="primary" loading={saving} onClick={handleSave}>
        保存
      </Button>
    </Space>
  );
}
