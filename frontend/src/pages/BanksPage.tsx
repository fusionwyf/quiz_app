// 题库管理页：题库列表、创建、导入导出、删除
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { createBank, deleteBank, exportUrl, listBanks } from '../api';
import type { QuestionBank } from '../api/types';
import ImportModal from '../components/ImportModal';

const { Text } = Typography;

export default function BanksPage() {
  const navigate = useNavigate();
  const [banks, setBanks] = useState<QuestionBank[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [importBank, setImportBank] = useState<QuestionBank | null>(null);

  const loadBanks = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const list = await listBanks(signal);
      if (!signal?.aborted) setBanks(list);
    } catch {
      // 错误提示已由拦截器处理
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 组件卸载/重新挂载时取消过期请求，避免旧响应覆盖新数据
    const controller = new AbortController();
    loadBanks(controller.signal);
    return () => controller.abort();
  }, [loadBanks]);

  // 创建弹窗重名预检（后端 409 为最终兜底）
  const trimmed = newName.trim();
  const duplicate = trimmed !== '' && banks.some((b) => b.name === trimmed);

  const handleCreate = async () => {
    const name = trimmed;
    if (!name) {
      message.warning('请输入题库名称');
      return;
    }
    setCreating(true);
    try {
      const created = await createBank(name);
      message.success('题库创建成功，马上导入题目吧');
      setCreateOpen(false);
      setNewName('');
      loadBanks();
      // 创建后直接进入导入流程，省去再找一遍题库卡片
      setImportBank(created);
    } catch {
      // 错误提示已由拦截器处理（如 409 重名）
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (bank: QuestionBank) => {
    try {
      await deleteBank(bank.id);
      message.success(`题库「${bank.name}」已删除`);
      loadBanks();
    } catch {
      // 错误提示已由拦截器处理
    }
  };

  return (
    <Spin spinning={loading}>
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

      {banks.length === 0 && !loading ? (
        <Empty description="暂无题库，点击右上角新建" />
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
                    onConfirm={() => handleDelete(bank)}
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
        confirmLoading={creating}
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

      {importBank && (
        <ImportModal
          open
          bankId={importBank.id}
          bankName={importBank.name}
          onClose={() => setImportBank(null)}
          onSuccess={loadBanks}
        />
      )}
    </Spin>
  );
}
