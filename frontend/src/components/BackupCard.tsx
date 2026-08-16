// 数据备份卡片：手动备份/恢复 + 每日自动备份列表（spec P1）
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Button,
  List,
  Modal,
  Space,
  Typography,
  Upload,
  message,
} from 'antd';
import { DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import type { UploadFile } from 'antd';
import {
  createBackup,
  listAutoBackups,
  restoreAutoBackup,
  restoreBackup,
} from '../api';
import { queryKeys } from '../api/queries';

const { Text } = Typography;

function downloadBlob(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function BackupCard() {
  const { data: backups = [], isLoading } = useQuery({
    queryKey: queryKeys.autoBackups,
    queryFn: listAutoBackups,
  });

  const backupMutation = useMutation({
    mutationFn: async () => {
      const payload = await createBackup();
      const now = new Date();
      const stamp = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(
        now.getDate(),
      ).padStart(2, '0')}-${String(now.getHours()).padStart(2, '0')}${String(
        now.getMinutes(),
      ).padStart(2, '0')}`;
      downloadBlob(
        JSON.stringify(payload, null, 2),
        `quiz-helper-backup-${stamp}.json`,
      );
      return payload;
    },
    onSuccess: () => message.success('备份文件已生成'),
  });

  const restoreMutation = useMutation({
    mutationFn: restoreBackup,
    onSuccess: (res) => {
      message.success(`${res.message}，页面即将刷新`);
      setTimeout(() => window.location.reload(), 800);
    },
  });

  const restoreAutoMutation = useMutation({
    mutationFn: restoreAutoBackup,
    onSuccess: (res) => {
      message.success(`${res.message}，页面即将刷新`);
      setTimeout(() => window.location.reload(), 800);
    },
  });

  const handleRestoreFile = (file: UploadFile) => {
    const raw = file.originFileObj;
    if (!raw) return;
    const reader = new FileReader();
    reader.onload = () => {
      let payload: unknown;
      try {
        payload = JSON.parse(String(reader.result));
      } catch {
        message.error('文件不是有效的 JSON 备份');
        return;
      }
      Modal.confirm({
        title: '确认恢复备份？',
        content:
          '恢复将覆盖当前全部数据（题库、题目、错题、答题记录、设置），覆盖前建议先做一次手动备份。此操作不可撤销。',
        okText: '覆盖恢复',
        okButtonProps: { danger: true },
        cancelText: '取消',
        onOk: () => restoreMutation.mutate(payload as Record<string, unknown>),
      });
    };
    reader.readAsText(raw);
    return false; // 阻止自动上传
  };

  const confirmAutoRestore = (filename: string, date: string) => {
    Modal.confirm({
      title: `从 ${date} 的自动备份恢复？`,
      content: '恢复将覆盖当前全部数据，此操作不可撤销。',
      okText: '覆盖恢复',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => restoreAutoMutation.mutate(filename),
    });
  };

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space wrap>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          loading={backupMutation.isPending}
          onClick={() => backupMutation.mutate()}
        >
          备份到文件
        </Button>
        <Upload
          accept=".json"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(file, fileList) => {
            if (fileList.length === 1) handleRestoreFile(file as UploadFile);
            return false;
          }}
        >
          <Button icon={<UploadOutlined />}>从文件恢复</Button>
        </Upload>
      </Space>
      <Text type="secondary">
        备份包含题库、题目、错题、答题记录与设置（AI 整理的 API Key
        不随备份带走，恢复后如需使用请重新配置）。
      </Text>

      <div>
        <Typography.Title level={5} style={{ marginTop: 8 }}>
          自动备份（每日首次启动，保留最近 7 份）
        </Typography.Title>
        <List
          size="small"
          loading={isLoading}
          locale={{ emptyText: '暂无自动备份，首次启动后生成' }}
          dataSource={backups}
          renderItem={(item) => (
            <List.Item
              actions={[
                <Button
                  key="restore"
                  type="link"
                  size="small"
                  onClick={() => confirmAutoRestore(item.filename, item.date)}
                >
                  恢复
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={item.date}
                description={`文件 ${item.filename} · ${formatSize(item.size_bytes)}`}
              />
            </List.Item>
          )}
        />
      </div>
    </Space>
  );
}
