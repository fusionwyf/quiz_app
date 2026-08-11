// 题目管理页：题库内题目表格 + 新增/编辑/删除
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Popconfirm,
  Space,
  Spin,
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
  exportQuestions,
  updateQuestion,
} from '../api';
import type {
  CreateQuestionDTO,
  Question,
  QuestionType,
} from '../api/types';
import { QUESTION_TYPE_LABELS } from '../api/types';
import QuestionFormModal from '../components/QuestionFormModal';

const TYPE_COLORS: Record<QuestionType, string> = {
  single: 'blue',
  multi: 'purple',
  judge: 'cyan',
  blank: 'orange',
};

export default function QuestionsPage() {
  const { bankId } = useParams<{ bankId: string }>();
  const navigate = useNavigate();
  const bankIdNum = Number(bankId);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [bankName, setBankName] = useState('');
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Question | null>(null);
  const [saving, setSaving] = useState(false);

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await exportQuestions(bankIdNum, { silent: true });
      setQuestions(res.questions);
      setBankName(res.bank_name);
    } catch {
      // 空题库 export 返回 404，按空列表处理
      setQuestions([]);
    } finally {
      setLoading(false);
    }
  }, [bankIdNum]);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  const handleSubmit = async (dto: CreateQuestionDTO) => {
    setSaving(true);
    try {
      if (editing) {
        const { bank_id, ...rest } = dto;
        void bank_id;
        await updateQuestion(editing.id, rest);
        message.success('题目已更新');
      } else {
        await createQuestion(dto);
        message.success('题目已创建');
      }
      setModalOpen(false);
      setEditing(null);
      loadQuestions();
    } catch {
      // 错误提示已由拦截器处理
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteQuestion(id);
      message.success('题目已删除');
      loadQuestions();
    } catch {
      // ignore
    }
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
            onConfirm={() => handleDelete(record.id)}
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
    <Spin spinning={loading}>
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
            {bankName || '题目管理'}（{questions.length} 题）
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
        pagination={{ pageSize: 20, showSizeChanger: false }}
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
      {saving && <Spin />}
    </Spin>
  );
}
