import React, { useState, useEffect } from 'react';
import { Select, Form, Input, Button, Card, Alert, Typography, Spin, message, InputNumber, Checkbox } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getTools, getTool, executeTool } from '../api';
import './TestTool.css';

const { Title, Text } = Typography;
const { Option } = Select;

function TestTool() {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [selectedTool, setSelectedTool] = useState(null);
  const [toolDetail, setToolDetail] = useState(null);
  const [result, setResult] = useState(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchTools();
  }, []);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const data = await getTools({ status: 'valid' });
      setTools(data);
    } catch (error) {
      message.error('获取工具列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToolSelect = async (toolId) => {
    setSelectedTool(toolId);
    setResult(null);
    form.resetFields(['arguments', 'caller']);
    
    const tool = tools.find(t => t.id === toolId);
    if (tool) {
      try {
        const detail = await getTool(tool.id);
        setToolDetail(detail);
      } catch (error) {
        message.error('获取工具详情失败');
      }
    }
  };

  const handleExecute = async (values) => {
    if (!toolDetail) return;

    setExecuting(true);
    setResult(null);
    try {
      const response = await executeTool({
        tool_name: toolDetail.name,
        arguments: values.arguments || {},
        caller: values.caller || null,
      });
      setResult(response);
    } catch (error) {
      message.error('执行失败');
    } finally {
      setExecuting(false);
    }
  };

  const renderInputField = (name, propInfo, required) => {
    const propType = propInfo.type || 'string';
    const label = `${name}${required ? ' *' : ''}`;
    const help = propInfo.description;

    switch (propType) {
      case 'integer':
        return (
          <Form.Item
            key={name}
            name={['arguments', name]}
            label={label}
            tooltip={help}
            rules={required ? [{ required: true, message: `请输入 ${name}` }] : []}
          >
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        );
      case 'number':
        return (
          <Form.Item
            key={name}
            name={['arguments', name]}
            label={label}
            tooltip={help}
            rules={required ? [{ required: true, message: `请输入 ${name}` }] : []}
          >
            <InputNumber style={{ width: '100%' }} />
          </Form.Item>
        );
      case 'boolean':
        return (
          <Form.Item
            key={name}
            name={['arguments', name]}
            label={label}
            tooltip={help}
            valuePropName="checked"
          >
            <Checkbox />
          </Form.Item>
        );
      default:
        return (
          <Form.Item
            key={name}
            name={['arguments', name]}
            label={label}
            tooltip={help}
            rules={required ? [{ required: true, message: `请输入 ${name}` }] : []}
          >
            <Input />
          </Form.Item>
        );
    }
  };

  const inputSchema = toolDetail?.input_schema || {};
  const properties = inputSchema.properties || {};
  const requiredFields = inputSchema.required || [];

  return (
    <div className="test-tool-container">
      <div className="test-header">
        <Title level={2}>测试工具</Title>
        <Text type="secondary">选择已验证的工具进行测试执行</Text>
      </div>

      <Spin spinning={loading}>
        <div className="test-content">
          <Card className="test-card">
            <Form form={form} layout="vertical" onFinish={handleExecute}>
              <Form.Item label="选择工具" required>
                <Select
                  placeholder="请选择要测试的工具"
                  value={selectedTool}
                  onChange={handleToolSelect}
                  showSearch
                  filterOption={(input, option) =>
                    option.children.toLowerCase().includes(input.toLowerCase())
                  }
                >
                  {tools.map((tool) => (
                    <Option key={tool.id} value={tool.id}>
                      {tool.name}
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              {toolDetail && (
                <>
                  <div className="tool-info">
                    <Text type="secondary">{toolDetail.description || '暂无描述'}</Text>
                  </div>

                  <div className="input-fields">
                    <Title level={5}>输入参数</Title>
                    {Object.entries(properties).map(([name, propInfo]) =>
                      renderInputField(name, propInfo, requiredFields.includes(name))
                    )}
                  </div>

                  <Form.Item name="caller" label="调用者（可选）">
                    <Input placeholder="您的名字" />
                  </Form.Item>

                  <Form.Item>
                    <Button
                      type="primary"
                      htmlType="submit"
                      icon={<PlayCircleOutlined />}
                      loading={executing}
                      block
                    >
                      执行工具
                    </Button>
                  </Form.Item>
                </>
              )}

              {tools.length === 0 && !loading && (
                <Alert
                  type="info"
                  message="暂无可用工具，请先上传并验证工具"
                  showIcon
                />
              )}
            </Form>
          </Card>

          {result && (
            <Card className="result-card" title="执行结果">
              {result.success ? (
                <div className="success-result">
                  <Alert
                    type="success"
                    message={`执行成功 (耗时: ${result.execution_time_ms}ms)`}
                    showIcon
                  />
                  <div className="result-content">
                    <Title level={5}>结果</Title>
                    <SyntaxHighlighter
                      language="text"
                      style={vscDarkPlus}
                    >
                      {result.result}
                    </SyntaxHighlighter>
                  </div>
                </div>
              ) : (
                <Alert
                  type="error"
                  message="执行失败"
                  description={result.error || '未知错误'}
                  showIcon
                />
              )}
            </Card>
          )}
        </div>
      </Spin>
    </div>
  );
}

export default TestTool;
