// 侧边菜单布局
import { useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Badge, Layout, Menu, theme } from 'antd';
import {
  BookOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  EditOutlined,
  FileTextOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { useMistakeCount } from '../api/queries';

const { Sider, Content, Header } = Layout;

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const mistakeCount = useMistakeCount();
  const { token } = theme.useToken();

  const menuItems = [
    { key: '/', icon: <DashboardOutlined />, label: '总览' },
    { key: '/banks', icon: <DatabaseOutlined />, label: '题库管理' },
    { key: '/quiz/start', icon: <EditOutlined />, label: '开始做题' },
    {
      key: '/mistakes',
      icon: (
        <Badge count={mistakeCount} size="small" offset={[8, 0]}>
          <BookOutlined />
        </Badge>
      ),
      label: '错题本',
    },
    { key: '/records', icon: <FileTextOutlined />, label: '答题记录' },
    { key: '/settings', icon: <SettingOutlined />, label: '系统设置' },
  ];

  // 子路由高亮父级菜单（做题相关页面统一高亮“开始做题”）
  const selectedKey = location.pathname.startsWith('/quiz')
    ? '/quiz/start'
    : menuItems.find(
        (item) => item.key !== '/' && location.pathname.startsWith(item.key),
      )?.key ?? '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
      >
        <div
          style={{
            color: '#fff',
            textAlign: 'center',
            fontSize: collapsed ? 16 : 18,
            fontWeight: 600,
            padding: '16px 8px',
          }}
        >
          {collapsed ? '刷' : '刷题助手'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            padding: '0 24px',
            fontSize: 16,
            fontWeight: 500,
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          刷题助手
        </Header>
        <Content style={{ padding: 24, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
