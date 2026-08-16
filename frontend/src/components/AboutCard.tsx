// 关于卡片：版本、仓库与反馈入口、许可与数据说明
import { useEffect, useState } from 'react';
import { Space, Typography } from 'antd';
import { ISSUES_URL, REPO_URL, RELEASES_URL, getAppVersion } from '../updates';

const { Text } = Typography;

export default function AboutCard() {
  const [version, setVersion] = useState<string>('…');
  useEffect(() => {
    getAppVersion()
      .then(setVersion)
      .catch(() => setVersion('—'));
  }, []);

  return (
    <Space direction="vertical" size="small">
      <Text strong>刷题助手 v{version}</Text>
      <Text type="secondary">
        本地、免费、离线的刷题桌面软件——答错自动进错题本，连对自动出本。
      </Text>
      <Space size="middle" wrap>
        <Typography.Link href={REPO_URL} target="_blank">
          源码仓库
        </Typography.Link>
        <Typography.Link href={RELEASES_URL} target="_blank">
          发布页
        </Typography.Link>
        <Typography.Link href={ISSUES_URL} target="_blank">
          问题反馈
        </Typography.Link>
      </Space>
      <Text type="secondary">
        遇到问题请在 Issue 附上「系统设置 → 诊断 → 导出诊断包」生成的 zip。开源协议
        MIT；所有数据仅存于本机（%APPDATA%\quiz-app\）。
      </Text>
    </Space>
  );
}
