// 应用内更新检查器（spec P2）：启动后台检查，有新版本时页头出现入口。
// 仅在 Tauri 桌面环境运行（浏览器 dev 模式自动跳过）；检查失败静默（提供手动下载兜底）。
import { useEffect, useState } from 'react';
import { Modal, Space, Tag, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

const RELEASES_URL = 'https://github.com/fusionwyf/quiz_app/releases';

function isDesktop(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

interface PendingUpdate {
  version: string;
  notes?: string;
  install: () => Promise<void>;
}

export default function UpdateChecker() {
  const [pending, setPending] = useState<PendingUpdate | null>(null);
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    if (!isDesktop()) return;
    let cancelled = false;
    (async () => {
      try {
        const { check } = await import('@tauri-apps/plugin-updater');
        const update = await check();
        if (!cancelled && update) {
          setPending({
            version: update.version,
            notes: update.body ?? undefined,
            install: async () => {
              await update.downloadAndInstall();
              const { relaunch } = await import('@tauri-apps/plugin-process');
              await relaunch();
            },
          });
        }
      } catch {
        // 网络失败等：静默，用户可从 README/手动链接获取新版
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!pending) return null;

  const handleInstall = async () => {
    setInstalling(true);
    try {
      await pending.install();
    } catch {
      message.error('自动更新失败，请到发布页手动下载');
      window.open(RELEASES_URL, '_blank');
    } finally {
      setInstalling(false);
    }
  };

  return (
    <>
      <Tag
        color="processing"
        style={{ cursor: 'pointer', marginInlineEnd: 0 }}
        onClick={() => Modal.confirm({ ...confirmProps(pending, handleInstall, installing) })}
      >
        <ReloadOutlined /> 新版本 v{pending.version}
      </Tag>
    </>
  );
}

function confirmProps(
  pending: PendingUpdate,
  onInstall: () => void,
  installing: boolean,
) {
  return {
    title: `升级到 v${pending.version}？`,
    content: (
      <Space direction="vertical">
        {pending.notes && (
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto', marginBottom: 0 }}>
            {pending.notes}
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
    onOk: onInstall,
  };
}
