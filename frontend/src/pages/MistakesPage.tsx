// 错题本页：错题列表与移除
import { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Empty,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined } from '@ant-design/icons';
import { getMistakeBook, unmarkMistake } from '../api';
import type { MistakeItem, QuestionType } from '../api/types';
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

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const list = await getMistakeBook(undefined, signal);
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
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const handleRemove = async (questionId: number) => {
    try {
      await unmarkMistake(questionId);
      message.success('已从错题本移除');
      load();
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
          title="确定从错题本移除？"
          onConfirm={() => handleRemove(record.question_id)}
          okText="移除"
          cancelText="取消"
        >
          <Button type="link" danger size="small">
            移除
          </Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          错题本（{mistakes.length} 题）
        </Typography.Title>
        <Button icon={<ReloadOutlined />} onClick={() => load()}>
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
