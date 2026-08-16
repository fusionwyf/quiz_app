// 错题本页：错题列表（可按题库筛选）与已掌握移出
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Empty,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined } from '@ant-design/icons';
import { getMistakeBook, listBanks, markMastered } from '../api';
import type { MistakeItem, QuestionBank, QuestionType } from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';

const TYPE_COLORS: Record<QuestionType, string> = {
  single: 'blue',
  multi: 'purple',
  judge: 'cyan',
  blank: 'orange',
};

export default function MistakesPage() {
  const [mistakes, setMistakes] = useState<MistakeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [banks, setBanks] = useState<QuestionBank[]>([]);
  const [bankId, setBankId] = useState<number | undefined>(undefined);

  const load = useCallback(async (signal?: AbortSignal, bank?: number) => {
    setLoading(true);
    try {
      const list = await getMistakeBook(bank, signal);
      setMistakes(list);
    } catch {
      // 忽略（含过期请求取消）
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 组件卸载/重新挂载时取消过期请求，避免旧响应覆盖新数据
    const controller = new AbortController();
    load(controller.signal, bankId);
    return () => controller.abort();
  }, [load, bankId]);

  useEffect(() => {
    listBanks()
      .then(setBanks)
      .catch(() => {});
  }, []);

  const handleMastered = async (questionId: number) => {
    try {
      await markMastered(questionId);
      message.success('已掌握，移出错题本');
      load(undefined, bankId);
    } catch {
      // ignore
    }
  };

  const columns: ColumnsType<MistakeItem> = [
    { title: '题目ID', dataIndex: 'question_id', width: 80 },
    { title: '题目内容', dataIndex: 'question_content', ellipsis: true },
    {
      title: '题型',
      dataIndex: 'question_type',
      width: 90,
      render: (type: QuestionType) => (
        <Tag color={TYPE_COLORS[type]}>
          {QUESTION_TYPE_LABELS[type] ?? type}
        </Tag>
      ),
    },
    {
      title: '错误次数',
      dataIndex: 'wrong_count',
      width: 90,
      sorter: (a, b) => a.wrong_count - b.wrong_count,
    },
    {
      title: '连续答对',
      dataIndex: 'consecutive_correct',
      width: 90,
      render: (v: number) =>
        v > 0 ? `${v} 次（连对达标自动出本）` : '—',
    },
    {
      title: '最后错误时间',
      dataIndex: 'last_wrong_at',
      width: 180,
      render: (t: string) => new Date(t).toLocaleString(),
    },
    {
      title: '操作',
      width: 100,
      render: (_, record) => (
        <Popconfirm
          title="确认已掌握这道题？"
          onConfirm={() => handleMastered(record.question_id)}
          okText="已掌握"
          cancelText="取消"
        >
          <Button type="link" size="small">
            已掌握
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Typography.Title level={4} style={{ margin: 0 }}>
            错题本（{mistakes.length} 题）
          </Typography.Title>
          <Select
            allowClear
            placeholder="全部题库"
            style={{ width: 180 }}
            value={bankId}
            onChange={(v) => setBankId(v)}
            options={banks.map((b) => ({ value: b.id, label: b.name }))}
          />
        </Space>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => load(undefined, bankId)}
        >
          刷新
        </Button>
      </Space>
      {mistakes.length === 0 && !loading ? (
        <Empty description="错题本是空的，继续保持" />
      ) : (
        <Table<MistakeItem>
          rowKey="mistake_id"
          columns={columns}
          dataSource={mistakes}
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      )}
    </Space>
  );
}
