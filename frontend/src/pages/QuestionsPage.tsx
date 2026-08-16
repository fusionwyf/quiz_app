// 题目管理页：题库内题目表格 + 新增/编辑/删除（取数经 TanStack Query，服务端分页）
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ArrowLeftOutlined, PlusOutlined } from '@ant-design/icons';
import {
  createQuestion,
  deleteQuestion,
  listQuestions,
  updateQuestion,
} from '../api';
import { queryKeys } from '../api/queries';
import { TYPE_COLORS } from '../constants';
import type {
  CreateQuestionDTO,
  Question,
  QuestionType,
} from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';
import QuestionFormModal from '../components/QuestionFormModal';

export default function QuestionsPage() {
  const { bankId } = useParams<{ bankId: string }>();
  const navigate = useNavigate();
  const bankIdNum = Number(bankId);
  const qc = useQueryClient();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Question | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isFetching } = useQuery({
    queryKey: queryKeys.questions(bankIdNum, page, pageSize),
    queryFn: () => listQuestions(bankIdNum, page, pageSize),
  });
  const questions = data?.questions ?? [];
  const total = data?.total ?? 0;
  const bankName = data?.bank_name ?? '';

  const invalidateLists = () => {
    qc.invalidateQueries({ queryKey: ['questions'] });
    qc.invalidateQueries({ queryKey: queryKeys.banks }); // 题目计数变化
  };

  const saveMutation = useMutation({
    mutationFn: (dto: CreateQuestionDTO) => {
      if (editing) {
        const { bank_id, ...rest } = dto;
        void bank_id;
        return updateQuestion(editing.id, rest);
      }
      return createQuestion(dto);
    },
    onSuccess: () => {
      message.success(editing ? '题目已更新' : '题目已创建');
      setModalOpen(false);
      setEditing(null);
      invalidateLists();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteQuestion(id),
    onSuccess: () => {
      message.success('题目已删除');
      // 删掉本页最后一条时回退一页，避免停留在空页
      if (questions.length === 1 && page > 1) setPage(page - 1);
      invalidateLists();
    },
  });

  const handleSubmit = async (dto: CreateQuestionDTO) => {
    saveMutation.mutate(dto);
  };

  const columns: ColumnsType<Question> = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    {
      title: '题型',
      dataIndex: 'type',
      width: 90,
      render: (type: QuestionType) => (
        <Tag color={TYPE_COLORS[type]}>
          {QUESTION_TYPE_LABELS[type] ?? type}
        </Tag>
      ),
    },
    { title: '题目内容', dataIndex: 'content', ellipsis: true },
    {
      title: '选项',
      dataIndex: 'options',
      width: 120,
      render: (options?: Record<string, string> | null) =>
        options ? Object.keys(options).sort().join(' / ') : '-',
    },
    {
      title: '答案',
      dataIndex: 'answer',
      width: 120,
      render: (answer?: string[] | null, record?: Question) =>
        (record?.type === 'blank'
          ? record.blank_answer
          : answer
        )?.join('、') ?? '-',
    },
    { title: '分数', dataIndex: 'score', width: 70 },
    {
      title: '操作',
      width: 140,
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => {
              setEditing(record);
              setModalOpen(true);
            }}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该题目？"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Space
        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}
      >
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/')}
          >
            返回
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {bankName || '题目管理'}（{total} 题）
          </Typography.Title>
        </Space>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditing(null);
            setModalOpen(true);
          }}
        >
          新增题目
        </Button>
      </Space>

      <Table<Question>
        rowKey="id"
        columns={columns}
        dataSource={questions}
        loading={isFetching}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: false,
          onChange: (p) => setPage(p),
        }}
      />

      {modalOpen && (
        <QuestionFormModal
          open
          bankId={bankIdNum}
          question={editing}
          onCancel={() => {
            setModalOpen(false);
            setEditing(null);
          }}
          onSubmit={handleSubmit}
        />
      )}
    </>
  );
}
