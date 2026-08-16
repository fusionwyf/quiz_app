// 外观主题设置表单（浅色/深色/跟随系统）
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Radio, Space, Typography, message } from 'antd';
import { useState } from 'react';
import { setThemeSetting } from '../api';
import type { ThemeMode } from '../api';
import { queryKeys } from '../api/queries';

const { Text } = Typography;

export default function ThemeForm({ current }: { current: ThemeMode }) {
  const [mode, setMode] = useState<ThemeMode>(current);
  const qc = useQueryClient();

  const saveMutation = useMutation({
    mutationFn: setThemeSetting,
    onSuccess: (saved) => {
      setMode(saved);
      qc.invalidateQueries({ queryKey: queryKeys.theme }); // App 级 ConfigProvider 随之切换
      message.success('已保存');
    },
  });

  return (
    <Space direction="vertical" size="small">
      <Radio.Group
        value={mode}
        onChange={(e) => {
          const value = e.target.value as ThemeMode;
          setMode(value);
          saveMutation.mutate(value);
        }}
        optionType="button"
        buttonStyle="solid"
      >
        <Radio value="system">跟随系统</Radio>
        <Radio value="light">浅色</Radio>
        <Radio value="dark">深色</Radio>
      </Radio.Group>
      <Text type="secondary">选择立即生效，并在本机记住。</Text>
    </Space>
  );
}
