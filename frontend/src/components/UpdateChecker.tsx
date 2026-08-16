// 页头更新入口：启动后台检查，有新版本时页头出现标签，点击确认后升级。
// 共享逻辑见 src/updates.ts；仅在 Tauri 桌面环境激活，检查失败静默。
import { useEffect, useState } from 'react';
import { Modal, Space, Tag, Typography, message } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { RELEASES_URL, checkForUpdate } from '../updates';
import type { AppUpdate } from '../updates';

export default function UpdateChecker() {
  const [pending, setPending] = useState<AppUpdate | null>(null);
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    let cancelled = false;
    import('../updates').then(async ({ isDesktopApp }) => {
      if (!isDesktopApp()) return;
      try {
        const update = await checkForUpdate();
        if (!cancelled) setPending(update);
      } catch {
        // 网络失败等：静默，用户可从设置页/README 手动获取新版
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!pending) return null;

  const handleInstall = async () => {
    setInstalling(true);
    try {
      await pending.downloadAndRestart();
    } catch {
      message.error('自动更新失败，请到发布页手动下载');
      window.open(RELEASES_URL, '_blank');
    } finally {
      setInstalling(false);
    }
  };

  return (
    <Tag
      color="processing"
      style={{ cursor: 'pointer', marginInlineEnd: 0 }}
      onClick={() =>
        Modal.confirm({
          title: `升级到 v${pending.version}？`,
          content: (
            <Space direction="vertical">
              {pending.notes && (
                <Typography.Paragraph
                  style={{ whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto', marginBottom: 0 }}
                >
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
          onOk: handleInstall,
        })
      }
    >
      <ReloadOutlined /> 新版本 v{pending.version}
    </Tag>
  );
}
