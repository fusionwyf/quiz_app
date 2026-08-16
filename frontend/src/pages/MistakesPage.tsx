// 错题本页：错题列表（可按题库筛选）与已掌握移出（取数经 TanStack Query）
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
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
import { markMastered } from '../api';
import { useBanks, useMistakeBook } from '../api/queries';
import { TYPE_COLORS } from '../constants';
import type { MistakeItem, QuestionType } from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';

export default function MistakesPage() {
  const [bankId, setBankId] = useState<number | undefined>(undefined);
  const { data: banks = [] } = useBanks();
  const { data: mistakes = [], isLoading, refetch } = useMistakeBook(bankId);

  const masteredMutation = useMutation({
    mutationFn: (questionId: number) => markMastered(questionId),
    onSuccess: () => message.success('已掌握，移出错题本'),
  });

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
          onConfirm={() => masteredMutation.mutate(record.question_id)}
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
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
          刷新
        </Button>
      </Space>
      {mistakes.length === 0 && !isLoading ? (
        <Empty description="错题本是空的，继续保持" />
      ) : (
        <Table<MistakeItem>
          rowKey="mistake_id"
          columns={columns}
          dataSource={mistakes}
          loading={isLoading}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      )}
    </Space>
  );
}
