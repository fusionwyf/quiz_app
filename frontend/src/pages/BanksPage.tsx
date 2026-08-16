// 题库管理页：题库列表、创建、导入导出、删除（取数经 TanStack Query）
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Row,
  Space,
  Spin,
  Typography,
  message,
} from 'antd';
import {
  DeleteOutlined,
  DownloadOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { createBank, deleteBank, exportUrl } from '../api';
import { queryKeys, useBanks } from '../api/queries';
import type { QuestionBank } from '../api/types';
import ImportModal from '../components/ImportModal';
import OnboardingModal, { shouldShowOnboarding } from '../components/OnboardingModal';

const { Text } = Typography;

export default function BanksPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: banks = [], isLoading } = useBanks();

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [importBank, setImportBank] = useState<QuestionBank | null>(null);
  // 首次引导：本地未见过引导标记且没有任何题库时展示（AC：完成后不再出现）
  const [onboardingOpen, setOnboardingOpen] = useState(shouldShowOnboarding);

  const createMutation = useMutation({
    mutationFn: createBank,
    onSuccess: (created) => {
      message.success('题库创建成功，马上导入题目吧');
      setCreateOpen(false);
      setNewName('');
      qc.invalidateQueries({ queryKey: queryKeys.banks });
      // 创建后直接进入导入流程，省去再找一遍题库卡片
      setImportBank(created);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (bankId: number) => deleteBank(bankId),
    onSuccess: (_data, bankId) => {
      const bank = banks.find((b) => b.id === bankId);
      message.success(`题库「${bank?.name ?? bankId}」已删除`);
      qc.invalidateQueries({ queryKey: queryKeys.banks });
    },
  });

  // 创建弹窗重名预检（后端 409 为最终兜底）
  const trimmed = newName.trim();
  const duplicate = trimmed !== '' && banks.some((b) => b.name === trimmed);

  const handleCreate = () => {
    if (!trimmed) {
      message.warning('请输入题库名称');
      return;
    }
    createMutation.mutate(trimmed);
  };

  return (
    <Spin spinning={isLoading}>
      <Space
        style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}
      >
        <Typography.Title level={4} style={{ margin: 0 }}>
          题库管理
        </Typography.Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
        >
          新建题库
        </Button>
      </Space>

      {banks.length === 0 && !isLoading ? (
        <Empty description="还没有题库，先建一个开始刷题吧">
          <Space>
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              新建题库
            </Button>
          </Space>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {banks.map((bank) => (
            <Col xs={24} sm={12} lg={8} key={bank.id}>
              <Card
                title={bank.name}
                extra={
                  <Text type="secondary">{bank.question_count ?? 0} 题</Text>
                }
                actions={[
                  <Button
                    type="link"
                    key="manage"
                    onClick={() => navigate(`/banks/${bank.id}/questions`)}
                  >
                    管理题目
                  </Button>,
                  <Button
                    type="link"
                    key="import"
                    icon={<UploadOutlined />}
                    onClick={() => setImportBank(bank)}
                  >
                    导入
                  </Button>,
                  <a key="json" href={exportUrl(bank.id, 'json')} target="_blank">
                    <DownloadOutlined /> JSON
                  </a>,
                  <a key="txt" href={exportUrl(bank.id, 'txt')} target="_blank">
                    <DownloadOutlined /> TXT
                  </a>,
                  <Popconfirm
                    key="delete"
                    title={`删除题库「${bank.name}」？`}
                    description="将同时删除库内题目、错题与答题记录，不可恢复"
                    okText="删除"
                    okButtonProps={{ danger: true }}
                    cancelText="取消"
                    onConfirm={() => deleteMutation.mutate(bank.id)}
                  >
                    <Button type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <Text type="secondary">
                  创建于 {new Date(bank.created_at).toLocaleString()}
                </Text>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="新建题库"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreate}
        confirmLoading={createMutation.isPending}
        okButtonProps={{ disabled: !trimmed || duplicate }}
        okText="创建"
        cancelText="取消"
      >
        <Input
          placeholder="请输入题库名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={handleCreate}
        />
        {duplicate && (
          <Text type="danger" style={{ fontSize: 12 }}>
            该名称已存在，请换一个
          </Text>
        )}
      </Modal>

      {onboardingOpen && banks.length === 0 && !isLoading && (
        <OnboardingModal onClose={() => setOnboardingOpen(false)} />
      )}

      {importBank && (
        <ImportModal
          open
          bankId={importBank.id}
          bankName={importBank.name}
          onClose={() => setImportBank(null)}
        />
      )}
    </Spin>
  );
}
