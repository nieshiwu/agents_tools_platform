import React, { useState } from 'react';
import { Form, Input, Button, Card, Alert, Typography, Space, message } from 'antd';
import { UploadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { createTool, validateTool } from '../api';
import './UploadTool.css';

const { TextArea } = Input;
const { Title, Text } = Typography;

const sampleCode = `from langchain_core.tools import tool

@tool
def my_tool(query: str) -> str:
    """工具描述
    
    Args:
        query: 输入参数
    
    Returns:
        处理结果
    """
    return f"处理结果: {query}"`;

function UploadTool() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  const handleValidate = async () => {
    const sourceCode = form.getFieldValue('source_code');
    if (!sourceCode) {
      message.warning('请输入源代码');
      return;
    }

    setValidating(true);
    setValidationResult(null);
    try {
      const result = await validateTool(sourceCode);
      setValidationResult(result);
    } catch (error) {
      message.error('验证失败');
    } finally {
      setValidating(false);
    }
  };

  const handleSubmit = async (values) => {
    setLoading(true);
    try {
      const result = await createTool({
        name: values.name,
        description: values.description || null,
        source_code: values.source_code,
        uploader: values.uploader || null,
      });
      
      if (result.status === 'valid') {
        message.success('工具上传成功！');
        form.resetFields();
        setValidationResult(null);
      } else {
        message.warning('工具已保存，但验证未通过');
      }
    } catch (error) {
      message.error('上传失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="upload-tool-container">
      <div className="upload-header">
        <Title level={2}>上传工具</Title>
        <Text type="secondary">上传您的 LangChain 工具代码，系统会自动验证是否符合规范</Text>
      </div>

      <div className="upload-content">
        <Card className="upload-form-card">
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
          >
            <Form.Item
              name="name"
              label="工具名称"
              rules={[{ required: true, message: '请输入工具名称' }]}
            >
              <Input placeholder="my_tool" />
            </Form.Item>

            <Form.Item
              name="description"
              label="工具描述"
            >
              <TextArea
                placeholder="这个工具用于..."
                rows={2}
              />
            </Form.Item>

            <Form.Item
              name="uploader"
              label="上传者"
            >
              <Input placeholder="您的名字（可选）" />
            </Form.Item>

            <Form.Item
              name="source_code"
              label="源代码"
              rules={[{ required: true, message: '请输入源代码' }]}
            >
              <TextArea
                placeholder={sampleCode}
                rows={15}
                className="code-input"
              />
            </Form.Item>

            {validationResult && (
              <div className="validation-result">
                {validationResult.is_valid ? (
                  <Alert
                    type="success"
                    icon={<CheckCircleOutlined />}
                    message="验证通过"
                    description={
                      <div>
                        <p>工具类型: {validationResult.tool_type}</p>
                        {validationResult.input_schema && (
                          <details>
                            <summary>输入参数 Schema</summary>
                            <SyntaxHighlighter language="json" style={vscDarkPlus}>
                              {JSON.stringify(validationResult.input_schema, null, 2)}
                            </SyntaxHighlighter>
                          </details>
                        )}
                      </div>
                    }
                    showIcon
                  />
                ) : (
                  <Alert
                    type="error"
                    icon={<CloseCircleOutlined />}
                    message="验证失败"
                    description={
                      <div>
                        {validationResult.errors?.map((err, i) => (
                          <p key={i} className="error-item">• {err}</p>
                        ))}
                        {validationResult.suggestions?.length > 0 && (
                          <div className="suggestions">
                            <strong>建议:</strong>
                            {validationResult.suggestions.map((sug, i) => (
                              <p key={i}>• {sug}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    }
                    showIcon
                  />
                )}
              </div>
            )}

            <Form.Item className="form-actions">
              <Space size="middle">
                <Button
                  onClick={handleValidate}
                  loading={validating}
                >
                  仅验证
                </Button>
                <Button
                  type="primary"
                  htmlType="submit"
                  icon={<UploadOutlined />}
                  loading={loading}
                >
                  上传工具
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
}

export default UploadTool;
