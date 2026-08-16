// 开始做题页：选择题库、题源（全部/错题）与题序（顺序/随机），创建 Session
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Form, Radio, Select, Space, Typography } from 'antd';
import { listBanks, startSession } from '../api';
import type { QuestionBank } from '../api/types';

export default function QuizStartPage() {
  const navigate = useNavigate();
  const [banks, setBanks] = useState<QuestionBank[]>([]);
  const [bankId, setBankId] = useState<number | undefined>();
  const [source, setSource] = useState<'normal' | 'mistake'>('normal');
  const [mode, setMode] = useState<'sequential' | 'random'>('sequential');
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    listBanks()
      .then((list) => {
        setBanks(list);
        if (list.length > 0) setBankId(list[0].id);
      })
      .catch(() => {});
  }, []);

  const handleStart = async () => {
    if (bankId === undefined) return;
    setStarting(true);
    try {
      const session = await startSession(bankId, mode, source);
      navigate(`/quiz/session/${session.id}`);
    } catch {
      // 错误提示已由拦截器处理（如题库无题/暂无错题返回 404）
    } finally {
      setStarting(false);
    }
  };

  return (
    <Card style={{ maxWidth: 520, margin: '40px auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          开始做题
        </Typography.Title>
        <Form layout="vertical">
          <Form.Item label="选择题库" required>
            <Select
              placeholder="请选择题库"
              value={bankId}
              onChange={setBankId}
              options={banks.map((b) => ({ value: b.id, label: b.name }))}
            />
          </Form.Item>
          <Form.Item label="练习来源">
            <Radio.Group
              value={source}
              onChange={(e) => setSource(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio value="normal">全部题目</Radio>
              <Radio value="mistake">错题本</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item label="做题模式">
            <Radio.Group
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              optionType="button"
              buttonStyle="solid"
            >
              <Radio value="sequential">顺序做题</Radio>
              <Radio value="random">随机出题</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
        <Button
          type="primary"
          size="large"
          block
          loading={starting}
          disabled={bankId === undefined}
          onClick={handleStart}
        >
          开始
        </Button>
      </Space>
    </Card>
  );
}
