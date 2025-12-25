import React, { useState, useEffect } from 'react';
import { Modal, Descriptions, Tag, Typography, Spin, Alert, Tabs } from 'antd';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getTool } from '../api';
import './ToolDetail.css';

const { Text, Paragraph } = Typography;

const statusConfig = {
  valid: { color: 'success', text: '有效' },
  invalid: { color: 'error', text: '无效' },
  pending: { color: 'warning', text: '待验证' },
  disabled: { color: 'default', text: '已禁用' },
};

function ToolDetail({ visible, tool, onClose }) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (visible && tool) {
      fetchDetail();
    }
  }, [visible, tool]);

  const fetchDetail = async () => {
    if (!tool) return;
    setLoading(true);
    try {
      const data = await getTool(tool.id);
      setDetail(data);
    } catch (error) {
      console.error('获取工具详情失败', error);
    } finally {
      setLoading(false);
    }
  };

  const status = detail ? statusConfig[detail.status] : statusConfig.pending;

  const tabItems = [
    {
      key: 'info',
      label: '基本信息',
      children: detail && (
        <Descriptions column={2} bordered size="small">
          <Descriptions.Item label="工具名称">{detail.name}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={status.color}>{status.text}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="工具类型">{detail.tool_type}</Descriptions.Item>
          <Descriptions.Item label="调用次数">{detail.call_count}</Descriptions.Item>
          <Descriptions.Item label="上传者">{detail.uploader || '匿名'}</Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {detail.created_at?.slice(0, 19)}
          </Descriptions.Item>
          <Descriptions.Item label="描述" span={2}>
            {detail.description || '暂无描述'}
          </Descriptions.Item>
          {detail.validation_message && (
            <Descriptions.Item label="验证信息" span={2}>
              <Alert
                type={detail.status === 'valid' ? 'success' : 'warning'}
                message={detail.validation_message}
                showIcon
              />
            </Descriptions.Item>
          )}
        </Descriptions>
      ),
    },
    {
      key: 'code',
      label: '源代码',
      children: detail && (
        <div className="code-container">
          <SyntaxHighlighter
            language="python"
            style={vscDarkPlus}
            showLineNumbers
            wrapLines
          >
            {detail.source_code}
          </SyntaxHighlighter>
        </div>
      ),
    },
    {
      key: 'schema',
      label: '输入参数',
      children: detail?.input_schema && (
        <div className="schema-container">
          <SyntaxHighlighter
            language="json"
            style={vscDarkPlus}
          >
            {JSON.stringify(detail.input_schema, null, 2)}
          </SyntaxHighlighter>
        </div>
      ),
    },
  ];

  return (
    <Modal
      title={`工具详情 - ${tool?.name || ''}`}
      open={visible}
      onCancel={onClose}
      width={900}
      footer={null}
      className="tool-detail-modal"
    >
      <Spin spinning={loading}>
        {detail && <Tabs items={tabItems} />}
      </Spin>
    </Modal>
  );
}

export default ToolDetail;
