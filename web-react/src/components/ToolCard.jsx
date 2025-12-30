import React from 'react';
import { Card, Tag, Typography, Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
  EyeOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  UserOutlined,
  CodeOutlined,
} from '@ant-design/icons';
import './ToolCard.css';

const { Text, Paragraph } = Typography;

const statusConfig = {
  valid: {
    color: '#52c41a',
    icon: <CheckCircleOutlined />,
    text: '有效',
    tagColor: 'success',
  },
  invalid: {
    color: '#ff4d4f',
    icon: <CloseCircleOutlined />,
    text: '无效',
    tagColor: 'error',
  },
  pending: {
    color: '#faad14',
    icon: <ClockCircleOutlined />,
    text: '待验证',
    tagColor: 'warning',
  },
  disabled: {
    color: '#8c8c8c',
    icon: <StopOutlined />,
    text: '已禁用',
    tagColor: 'default',
  },
};

const toolTypeIcons = {
  decorator: '🎯',
  class: '📦', 
  structured: '🔧',
  calculator: '🔢',
  text: '📝',
  weather: '🌤️',
  password: '🔐',
  json: '📄',
  unknown: '🛠️',
};

function ToolCard({ tool, onView, onDelete }) {
  const status = statusConfig[tool.status] || statusConfig.pending;
  const typeIcon = toolTypeIcons[tool.tool_type] || toolTypeIcons[tool.name?.includes('calculator') ? 'calculator' : tool.name?.includes('password') ? 'password' : tool.name?.includes('weather') ? 'weather' : tool.name?.includes('json') ? 'json' : 'unknown'];

  return (
    <Card
      className="tool-card"
      hoverable
      onClick={onView}
    >
      {/* 工具图标区域 */}
      <div className="tool-card-icon" style={{ borderColor: status.color }}>
        <span className="tool-icon-emoji">{typeIcon}</span>
      </div>

      {/* 工具名称 */}
      <div className="tool-card-title">
        <Tooltip title={tool.name}>
          <Text strong ellipsis className="tool-name">
            {tool.name}
          </Text>
        </Tooltip>
      </div>

      {/* 工具描述 */}
      <Paragraph
        ellipsis={{ rows: 2 }}
        className="tool-card-description"
      >
        {tool.description || '暂无描述'}
      </Paragraph>

      {/* 状态标签 */}
      <div className="tool-card-status">
        <Tag color={status.tagColor} icon={status.icon}>
          {status.text}
        </Tag>
      </div>

      {/* 底部信息 */}
      <div className="tool-card-footer">
        <div className="tool-meta">
          <Tooltip title="调用次数">
            <span className="meta-item">
              <ThunderboltOutlined /> {tool.call_count}
            </span>
          </Tooltip>
          <Tooltip title={`上传者: ${tool.uploader || '匿名'}`}>
            <span className="meta-item">
              <UserOutlined /> {tool.uploader || '匿名'}
            </span>
          </Tooltip>
        </div>
      </div>

      {/* 操作按钮（悬停显示） */}
      <div className="tool-card-actions" onClick={(e) => e.stopPropagation()}>
        <Tooltip title="查看详情">
          <button className="action-btn view-btn" onClick={onView}>
            <EyeOutlined />
          </button>
        </Tooltip>
        <Tooltip title="删除">
          <button className="action-btn delete-btn" onClick={onDelete}>
            <DeleteOutlined />
          </button>
        </Tooltip>
      </div>
    </Card>
  );
}

export default ToolCard;
