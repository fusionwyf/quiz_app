// 答题页：当前题目、提交判题、进度展示、完成总结
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Empty,
  Popconfirm,
  Progress,
  Result,
  Row,
  Space,
  Spin,
  Statistic,
  Typography,
  message,
} from 'antd';
import {
  getCurrentQuestion,
  getSessionStatus,
  finishSession,
  markMistake,
  submitAnswer,
} from '../api';
import type {
  CheckResult,
  QuestionDTO,
  SessionStatus,
  SessionSummary,
} from '../api/types';
import QuestionCard from '../components/QuestionCard';

type Phase = 'playing' | 'done';

export default function QuizPlayPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const sessionIdNum = Number(sessionId);

  const [phase, setPhase] = useState<Phase>('playing');
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [question, setQuestion] = useState<QuestionDTO | null>(null);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [mistakeMarked, setMistakeMarked] = useState(false);

  // 初始化：加载 Session 状态与当前题目
  useEffect(() => {
    (async () => {
      try {
        const st = await getSessionStatus(sessionIdNum);
        setStatus(st);
        if (st.finished) {
          setPhase('done');
        } else {
          const q = await getCurrentQuestion(sessionIdNum);
          setQuestion(q);
        }
      } catch {
        setLoadError(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [sessionIdNum]);

  const handleSubmit = useCallback(
    async (choices: string[]) => {
      if (!question) return;
      setSubmitting(true);
      try {
        const res = await submitAnswer(sessionIdNum, {
          question_id: question.id,
          user_choices: choices,
        });
        setResult(res);
        setMistakeMarked(false);
        const st = await getSessionStatus(sessionIdNum);
        setStatus(st);
      } catch {
        // ignore
      } finally {
        setSubmitting(false);
      }
    },
    [question, sessionIdNum],
  );

  const handleNext = useCallback(async () => {
    setResult(null);
    try {
      const q = await getCurrentQuestion(sessionIdNum);
      setQuestion(q);
    } catch {
      // ignore
    }
  }, [sessionIdNum]);

  const handleEarlyFinish = async () => {
    try {
      const sum = await finishSession(sessionIdNum);
      setSummary(sum);
    } catch {
      // ignore
    }
    setPhase('done');
  };

  const handleMarkMistake = async () => {
    if (!question || !status) return;
    try {
      await markMistake(question.id, status.bank_id);
      setMistakeMarked(true);
      message.success('已加入错题本');
    } catch {
      // ignore
    }
  };

  if (loading) {
    return <Spin style={{ display: 'block', margin: '80px auto' }} />;
  }

  if (loadError) {
    return (
      <Empty description="Session 不存在或已失效">
        <Button type="primary" onClick={() => navigate('/quiz/start')}>
          重新开始
        </Button>
      </Empty>
    );
  }

  // ===== 完成总结界面 =====
  if (phase === 'done' && status) {
    const answered = summary ? summary.answered_questions : status.current_index;
    const correct = summary ? summary.correct_count : status.correct_count;
    const score = summary ? summary.total_score_obtained : status.total_score;
    const accuracy = summary
      ? summary.accuracy_percentage
      : answered > 0
        ? (correct / answered) * 100
        : 0;

    return (
      <Result
        status="success"
        title="做题完成"
        subTitle={`共 ${status.total} 题，作答 ${answered} 题`}
        extra={[
          <Button
            type="primary"
            key="again"
            onClick={() => navigate('/quiz/start')}
          >
            再来一组
          </Button>,
          <Button key="records" onClick={() => navigate('/records')}>
            查看答题记录
          </Button>,
          <Button key="mistakes" onClick={() => navigate('/mistakes')}>
            查看错题本
          </Button>,
        ]}
      >
        <Row gutter={24}>
          <Col span={6}>
            <Statistic title="正确率" value={accuracy} precision={1} suffix="%" />
          </Col>
          <Col span={6}>
            <Statistic title="答对" value={correct} suffix="题" />
          </Col>
          <Col span={6}>
            <Statistic title="获得得分" value={score} precision={1} />
          </Col>
          <Col span={6}>
            <Statistic
              title="满分"
              value={summary ? summary.max_possible_score : '-'}
              precision={summary ? 1 : 0}
            />
          </Col>
        </Row>
      </Result>
    );
  }

  if (!status || !question) {
    return <Empty description="加载失败" />;
  }

  const isLastAnswered = status.finished && result !== null;

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card size="small">
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Typography.Text>
            第 {Math.min(status.current_index + 1, status.total)} /{' '}
            {status.total} 题 · 已答对 {status.correct_count} 题 · 累计得分{' '}
            {status.total_score}
          </Typography.Text>
          {!status.finished && (
            <Popconfirm
              title="确定提前结束做题？"
              onConfirm={handleEarlyFinish}
              okText="结束"
              cancelText="取消"
            >
              <Button size="small" danger>
                提前交卷
              </Button>
            </Popconfirm>
          )}
        </Space>
        <Progress percent={status.progress_percentage} size="small" />
      </Card>

      <QuestionCard
        key={question.id}
        question={question}
        result={result}
        submitting={submitting}
        onSubmit={handleSubmit}
      />

      {result && (
        <Space>
          {isLastAnswered ? (
            <Button type="primary" size="large" onClick={() => setPhase('done')}>
              查看结果
            </Button>
          ) : (
            <Button type="primary" size="large" onClick={handleNext}>
              下一题
            </Button>
          )}
          {!result.is_correct && !mistakeMarked && (
            <Button size="large" onClick={handleMarkMistake}>
              加入错题本
            </Button>
          )}
        </Space>
      )}
    </Space>
  );
}
