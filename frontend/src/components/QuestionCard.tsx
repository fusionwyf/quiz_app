// 题目卡片：展示题目并作答（单选/多选/判断/填空四种题型）
import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Input,
  Radio,
  Space,
  Tag,
  Typography,
} from 'antd';
import type { CheckResult, QuestionDTO } from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';
import { TYPE_COLORS } from '../constants';

const { Paragraph } = Typography;

interface QuestionCardProps {
  question: QuestionDTO;
  onSubmit: (choices: string[]) => void;
  submitting?: boolean;
  /** 提交后传入判题结果，卡片进入只读反馈态 */
  result?: CheckResult | null;
}

export default function QuestionCard({
  question,
  onSubmit,
  submitting,
  result,
}: QuestionCardProps) {
  const [choices, setChoices] = useState<string[]>([]);
  const [blankInput, setBlankInput] = useState('');
  const locked = result != null;

  // 切换题目时重置作答状态（父组件应使用 key={question.id}）
  useEffect(() => {
    setChoices([]);
    setBlankInput('');
  }, [question.id]);

  const optionKeys = Object.keys(question.options ?? {}).sort();

  const handleSubmit = () => {
    if (question.type === 'blank') {
      onSubmit([blankInput.trim()]);
    } else {
      onSubmit(choices);
    }
  };

  const renderBody = () => {
    switch (question.type) {
      case 'single':
        return (
          <Radio.Group
            value={choices[0]}
            disabled={locked}
            onChange={(e) => setChoices([e.target.value])}
          >
            <Space direction="vertical" size="middle">
              {optionKeys.map((key) => (
                <Radio key={key} value={key}>
                  {key}. {question.options?.[key]}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        );
      case 'multi':
        return (
          <Checkbox.Group
            value={choices}
            disabled={locked}
            onChange={(vals) => setChoices(vals as string[])}
          >
            <Space direction="vertical" size="middle">
              {optionKeys.map((key) => (
                <Checkbox key={key} value={key}>
                  {key}. {question.options?.[key]}
                </Checkbox>
              ))}
            </Space>
          </Checkbox.Group>
        );
      case 'judge':
        return (
          <Radio.Group
            value={choices[0]}
            disabled={locked}
            onChange={(e) => setChoices([e.target.value])}
          >
            <Space size="large">
              <Radio value="对">对</Radio>
              <Radio value="错">错</Radio>
            </Space>
          </Radio.Group>
        );
      case 'blank':
        return (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Input
              placeholder="请输入答案（注意与库内答案的大小写一致）"
              value={blankInput}
              disabled={locked}
              onChange={(e) => setBlankInput(e.target.value)}
              onPressEnter={handleSubmit}
            />
          </Space>
        );
      default:
        return <Alert type="error" message={`未知题型: ${question.type}`} />;
    }
  };

  const canSubmit =
    !locked &&
    (question.type === 'blank' ? blankInput.trim() !== '' : choices.length > 0);

  return (
    <Card>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Space align="start">
          <Tag color={TYPE_COLORS[question.type]}>
            {QUESTION_TYPE_LABELS[question.type] ?? question.type}
          </Tag>
          <Tag>{question.score} 分</Tag>
        </Space>
        <Paragraph style={{ fontSize: 16, marginBottom: 0 }}>
          {question.question}
        </Paragraph>
        {renderBody()}
        {!locked && (
          <Button
            type="primary"
            loading={submitting}
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            提交答案
          </Button>
        )}
        {result && (
          <Alert
            type={result.is_correct ? 'success' : 'error'}
            showIcon
            message={
              result.is_correct
                ? `回答正确，获得 ${result.score_obtained} 分`
                : '回答错误'
            }
            description={`正确答案：${result.correct_answer.join('、') || '无'}`}
          />
        )}
      </Space>
    </Card>
  );
}
