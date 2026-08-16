// 诊断卡片：打开日志目录 + 导出诊断包（spec P1）
import { Button, Space, Typography } from 'antd';
import { ExportOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { diagnosticsExportUrl, openLogFolder } from '../api';

const { Text } = Typography;

export default function DiagnosticsCard() {
  const handleOpen = async () => {
    try {
      await openLogFolder();
    } catch {
      // 错误提示已由拦截器处理
    }
  };

  return (
    <Space direction="vertical" size="small">
      <Space wrap>
        <Button icon={<FolderOpenOutlined />} onClick={handleOpen}>
          打开日志目录
        </Button>
        <a href={diagnosticsExportUrl()}>
          <Button icon={<ExportOutlined />}>导出诊断包</Button>
        </a>
      </Space>
      <Text type="secondary">
        遇到问题时，把诊断包（日志 + 版本 + 系统信息的 zip）附到 GitHub
        Issue 里，方便定位原因。日志只保存在本机，不会自动上传。
      </Text>
    </Space>
  );
}
