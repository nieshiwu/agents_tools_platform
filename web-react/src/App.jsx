import React, { useState } from 'react';
import { Layout, Menu, Typography } from 'antd';
import {
  AppstoreOutlined,
  UploadOutlined,
  PlayCircleOutlined,
  BookOutlined,
  BarChartOutlined,
  ToolOutlined,
} from '@ant-design/icons';
import ToolList from './components/ToolList';
import UploadTool from './components/UploadTool';
import TestTool from './components/TestTool';
import Documentation from './components/Documentation';
import Statistics from './components/Statistics';
import './App.css';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  {
    key: 'tools',
    icon: <AppstoreOutlined />,
    label: '工具列表',
  },
  {
    key: 'upload',
    icon: <UploadOutlined />,
    label: '上传工具',
  },
  {
    key: 'test',
    icon: <PlayCircleOutlined />,
    label: '测试工具',
  },
  {
    key: 'docs',
    icon: <BookOutlined />,
    label: '规范文档',
  },
  {
    key: 'stats',
    icon: <BarChartOutlined />,
    label: '统计信息',
  },
];

function App() {
  const [currentPage, setCurrentPage] = useState('tools');

  const renderContent = () => {
    switch (currentPage) {
      case 'tools':
        return <ToolList />;
      case 'upload':
        return <UploadTool />;
      case 'test':
        return <TestTool />;
      case 'docs':
        return <Documentation />;
      case 'stats':
        return <Statistics />;
      default:
        return <ToolList />;
    }
  };

  return (
    <Layout className="app-layout">
      <Header className="app-header">
        <div className="logo">
          <ToolOutlined className="logo-icon" />
          <Title level={4} className="logo-text">LangChain 工具平台</Title>
        </div>
        <div className="header-info">
          <span className="mcp-endpoint">MCP: http://localhost:7000/api/mcp</span>
        </div>
      </Header>
      <Layout>
        <Sider width={200} className="app-sider">
          <Menu
            mode="inline"
            selectedKeys={[currentPage]}
            items={menuItems}
            onClick={({ key }) => setCurrentPage(key)}
            className="side-menu"
          />
        </Sider>
        <Content className="app-content">
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  );
}

export default App;
