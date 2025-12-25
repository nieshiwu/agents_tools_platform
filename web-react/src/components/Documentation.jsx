import React, { useState, useEffect } from 'react';
import { Typography, Tabs, Card } from 'antd';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { getSpec } from '../api';
import './Documentation.css';

const { Title, Paragraph } = Typography;

const decoratorExample = `from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """计算数学表达式
    
    Args:
        expression: 数学表达式，如 "2 + 3 * 4"
    
    Returns:
        计算结果
    """
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"`;

const classExample = `from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type

class WeatherInput(BaseModel):
    """天气查询输入参数"""
    city: str = Field(description="城市名称")

class WeatherTool(BaseTool):
    """天气查询工具"""
    name: str = "weather"
    description: str = "查询指定城市的天气信息"
    args_schema: Type[BaseModel] = WeatherInput
    
    def _run(self, city: str) -> str:
        """执行天气查询"""
        # 这里应该调用真实的天气API
        return f"{city}的天气: 晴天，温度25°C"
    
    async def _arun(self, city: str) -> str:
        """异步执行"""
        return self._run(city)`;

function Documentation() {
  const [spec, setSpec] = useState('');

  useEffect(() => {
    fetchSpec();
  }, []);

  const fetchSpec = async () => {
    try {
      const data = await getSpec();
      setSpec(data.specification);
    } catch (error) {
      console.error('获取规范文档失败', error);
    }
  };

  const tabItems = [
    {
      key: 'decorator',
      label: '@tool 装饰器',
      children: (
        <div className="code-example">
          <Paragraph>使用 @tool 装饰器是创建工具最简单的方式，适合简单的函数型工具。</Paragraph>
          <SyntaxHighlighter language="python" style={vscDarkPlus} showLineNumbers>
            {decoratorExample}
          </SyntaxHighlighter>
        </div>
      ),
    },
    {
      key: 'class',
      label: 'BaseTool 类',
      children: (
        <div className="code-example">
          <Paragraph>继承 BaseTool 类可以创建更复杂的工具，支持更多自定义选项。</Paragraph>
          <SyntaxHighlighter language="python" style={vscDarkPlus} showLineNumbers>
            {classExample}
          </SyntaxHighlighter>
        </div>
      ),
    },
  ];

  return (
    <div className="documentation-container">
      <div className="doc-header">
        <Title level={2}>规范文档</Title>
      </div>

      <div className="doc-content">
        <Card className="spec-card">
          <Title level={4}>LangChain 工具规范</Title>
          <div className="spec-content" dangerouslySetInnerHTML={{ __html: spec.replace(/\n/g, '<br/>') }} />
        </Card>

        <Card className="examples-card">
          <Title level={4}>示例代码</Title>
          <Tabs items={tabItems} />
        </Card>
      </div>
    </div>
  );
}

export default Documentation;
