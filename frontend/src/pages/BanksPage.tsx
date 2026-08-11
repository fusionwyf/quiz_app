// 题库管理页：题库列表、创建、导入导出入口
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  Modal,
  Row,
  Space,
  Spin,
  Typography,
  message,
} from 'antd';
import {
  DownloadOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { createBank, exportQuestions, exportUrl, listBanks } from '../api';
import type { QuestionBank } from '../api/types';
import ImportModal from '../components/ImportModal';

const { Text } = Typography;

export default function BanksPage() {
  const navigate = useNavigate();
  const [banks, setBanks] = useState<QuestionBank[]>([]);
  const [counts, setCounts] = useState<Record<number, number>>({});
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);
  const [importBank, setImportBank] = useState<QuestionBank | null>(null);

  const loadBanks = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const list = await listBanks(signal);
      setBanks(list);
      // 题目数通过 export json 获取（空题库会返回 404，静默计为 0）
      const results = await Promise.allSettled(
        list.map((b) =>
          exportQuestions(b.id, { silent: true, signal }),
        ),
      );
      const map: Record<number, number> = {};
      results.forEach((r, i) => {
        map[list[i].id] =
          r.status === 'fulfilled' ? r.value.question_count : 0;
      });
      setCounts(map);
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

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      message.warning('请输入题库名称');
      return;
    }
    setCreating(true);
    try {
      await createBank(name);
      message.success('题库创建成功');
      setCreateOpen(false);
      setNewName('');
      loadBanks();
    } catch {
      // ignore
    } finally {
      setCreating(false);
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
                extra={<Text type="secondary">{counts[bank.id] ?? 0} 题</Text>}
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
        okText="创建"
        cancelText="取消"
      >
        <Input
          placeholder="请输入题库名称"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          onPressEnter={handleCreate}
        />
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
