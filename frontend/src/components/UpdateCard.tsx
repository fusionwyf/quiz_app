// 软件更新卡片：显示当前版本 + 手动检查更新（页头为自动检查，这里可主动触发）
import { useEffect, useState } from 'react';
import { Button, Modal, Space, Typography, message } from 'antd';
import { SafetyOutlined, SyncOutlined } from '@ant-design/icons';
import {
  RELEASES_URL,
  checkForUpdate,
  getAppVersion,
  isDesktopApp,
} from '../updates';
import type { AppUpdate } from '../updates';

export default function UpdateCard() {
  const [version, setVersion] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [result, setResult] = useState<'latest' | 'failed' | null>(null);

  useEffect(() => {
    getAppVersion()
      .then(setVersion)
      .catch(() => setVersion('—'));
  }, []);

  const installUpdate = (update: AppUpdate) => {
    Modal.confirm({
      title: `升级到 v${update.version}？`,
      content: (
        <Space direction="vertical">
          {update.notes && (
            <Typography.Paragraph
              style={{ whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto', marginBottom: 0 }}
            >
              {update.notes}
            </Typography.Paragraph>
          )}
          <Typography.Text type="secondary">
            下载并安装后应用会自动重启；题库与错题数据不受影响。
          </Typography.Text>
        </Space>
      ),
      okText: '下载并安装',
      cancelText: '暂不',
      okButtonProps: { loading: installing },
      onOk: async () => {
        setInstalling(true);
        try {
          await update.downloadAndRestart();
        } catch {
          message.error('自动更新失败，请到发布页手动下载');
          window.open(RELEASES_URL, '_blank');
        } finally {
          setInstalling(false);
        }
      },
    });
  };

  const handleCheck = async () => {
    if (!isDesktopApp()) {
      message.info('浏览器开发模式下不可自动更新，请前往发布页下载');
      window.open(RELEASES_URL, '_blank');
      return;
    }
    setChecking(true);
    setResult(null);
    try {
      const update = await checkForUpdate();
      if (update) {
        installUpdate(update);
      } else {
        setResult('latest');
      }
    } catch {
      setResult('failed');
    } finally {
      setChecking(false);
    }
  };

  return (
    <Space direction="vertical" size="small">
      <Space wrap>
        <Button
          type="primary"
          icon={<SyncOutlined />}
          loading={checking}
          onClick={handleCheck}
        >
          检查更新
        </Button>
        <Typography.Text type="secondary">
          当前版本 v{version ?? '…'}
        </Typography.Text>
      </Space>
      {result === 'latest' && (
        <Typography.Text type="success">
          <SafetyOutlined /> 已是最新版本
        </Typography.Text>
      )}
      {result === 'failed' && (
        <Typography.Text type="warning">
          检查失败（网络问题？），可到发布页手动下载
        </Typography.Text>
      )}
      <Typography.Text type="secondary">
        启动时会自动检查，有新版本时页头会出现升级入口；也可随时到
        <Typography.Link href={RELEASES_URL} target="_blank">
          发布页
        </Typography.Link>
        手动下载。
      </Typography.Text>
    </Space>
  );
}
