// 答题记录页：分页记录表格 + 正确性筛选 + 题目统计弹窗
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Modal,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Col,
  Row,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { BarChartOutlined, ReloadOutlined } from '@ant-design/icons';
import { getQuestionStats, getRecords } from '../api';
import type {
  ExamRecordItem,
  QuestionStats,
  QuestionType,
} from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';

const { Title, Paragraph } = Typography;

const TYPE_COLORS: Record<QuestionType, string> = {
  single: 'blue',
  multi: 'purple',
  judge: 'cyan',
  blank: 'orange',
};

type CorrectFilter = 'all' | 'correct' | 'wrong';

export default function RecordsPage() {
  const [records, setRecords] = useState<ExamRecordItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [filter, setFilter] = useState<CorrectFilter>('all');
  const [loading, setLoading] = useState(true);

  const [statsOpen, setStatsOpen] = useState(false);
  const [stats, setStats] = useState<QuestionStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      try {
        const data = await getRecords(
          {
            page,
            page_size: pageSize,
            is_correct:
              filter === 'all' ? undefined : filter === 'correct',
          },
          signal,
        );
        setRecords(data.records);
        setTotal(data.total);
      } catch {
        // 忽略（含过期请求取消）
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [page, pageSize, filter],
  );

  useEffect(() => {
    // 分页/筛选变化或组件重新挂载时取消过期请求，避免旧响应覆盖新数据
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const showStats = async (questionId: number) => {
    setStatsOpen(true);
    setStats(null);
    setStatsLoading(true);
    try {
      const data = await getQuestionStats(questionId);
      setStats(data);
    } catch {
      setStatsOpen(false);
    } finally {
      setStatsLoading(false);
    }
  };

  const columns: ColumnsType<ExamRecordItem> = [
    {
      title: '题目',
      dataIndex: 'question_content',
      key: 'question_content',
      ellipsis: true,
      render: (text: string | null | undefined, record) =>
        text ?? `题目 #${record.question_id}`,
    },
    {
      title: '题型',
      dataIndex: 'question_type',
      key: 'question_type',
      width: 100,
      render: (type: QuestionType | null | undefined) =>
        type ? (
          <Tag color={TYPE_COLORS[type]}>
            {QUESTION_TYPE_LABELS[type]}
          </Tag>
        ) : (
          '-'
        ),
    },
    {
      title: '我的答案',
      dataIndex: 'user_answer',
      key: 'user_answer',
      width: 140,
      render: (answers: string[]) => answers.join(', '),
    },
    {
      title: '结果',
      dataIndex: 'is_correct',
      key: 'is_correct',
      width: 90,
      render: (correct: boolean) =>
        correct ? (
          <Tag color="success">正确</Tag>
        ) : (
          <Tag color="error">错误</Tag>
        ),
    },
    {
      title: '作答时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => text.replace('T', ' ').slice(0, 19),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<BarChartOutlined />}
          onClick={() => showStats(record.question_id)}
        >
          统计
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 16 }} wrap>
        <Title level={4} style={{ margin: 0 }}>
          答题记录
        </Title>
        <Select
          value={filter}
          style={{ width: 130 }}
          options={[
            { value: 'all', label: '全部' },
            { value: 'correct', label: '仅正确' },
            { value: 'wrong', label: '仅错误' },
          ]}
          onChange={(value) => {
            setFilter(value);
            setPage(1);
          }}
        />
        <Button icon={<ReloadOutlined />} onClick={() => load()}>
          刷新
        </Button>
      </Space>
      <Table
        rowKey="id"
        columns={columns}
        dataSource={records}
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条记录`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />

      <Modal
        title="题目统计"
        open={statsOpen}
        onCancel={() => setStatsOpen(false)}
        footer={null}
        loading={statsLoading}
      >
        {stats && (
          <>
            <Paragraph>{stats.question_content}</Paragraph>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic title="总作答次数" value={stats.total_attempts} />
              </Col>
              <Col span={8}>
                <Statistic
                  title="正确率"
                  value={stats.correct_rate}
                  precision={1}
                  suffix="%"
                  valueStyle={{
                    color: stats.correct_rate >= 60 ? '#3f8600' : '#cf1322',
                  }}
                />
              </Col>
              <Col span={8}>
                <Statistic
                  title="平均得分"
                  value={stats.average_score}
                  precision={2}
                />
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 16 }}>
              <Col span={8}>
                <Statistic title="答对" value={stats.correct_attempts} />
              </Col>
              <Col span={8}>
                <Statistic title="答错" value={stats.wrong_attempts} />
              </Col>
              <Col span={8}>
                <Statistic
                  title="累计得分"
                  value={stats.total_score_obtained}
                  suffix={`/ ${stats.total_possible_score}`}
                />
              </Col>
            </Row>
          </>
        )}
      </Modal>
    </div>
  );
}
