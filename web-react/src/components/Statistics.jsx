import React, { useState, useEffect } from 'react';
import { Row, Col, Card, Statistic, Typography, Progress, Empty, Spin } from 'antd';
import {
  ToolOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { getStatistics, getTools } from '../api';
import './Statistics.css';

const { Title } = Typography;

function Statistics() {
  const [stats, setStats] = useState(null);
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsData, toolsData] = await Promise.all([
        getStatistics(),
        getTools(),
      ]);
      setStats(statsData);
      setTools(toolsData);
    } catch (error) {
      console.error('获取统计数据失败', error);
    } finally {
      setLoading(false);
    }
  };

  // 计算状态分布
  const getStatusCounts = () => {
    const counts = { valid: 0, invalid: 0, pending: 0, disabled: 0 };
    tools.forEach((tool) => {
      if (counts.hasOwnProperty(tool.status)) {
        counts[tool.status]++;
      }
    });
    return counts;
  };

  // 获取调用排行
  const getTopTools = () => {
    return [...tools]
      .sort((a, b) => b.call_count - a.call_count)
      .slice(0, 10);
  };

  const statusCounts = getStatusCounts();
  const topTools = getTopTools();
  const maxCalls = topTools.length > 0 ? topTools[0].call_count : 1;

  return (
    <div className="statistics-container">
      <div className="stats-header">
        <Title level={2}>统计信息</Title>
      </div>

      <Spin spinning={loading}>
        {stats && (
          <>
            <Row gutter={[24, 24]} className="stats-cards">
              <Col xs={24} sm={12} md={6}>
                <Card className="stat-card total">
                  <Statistic
                    title="总工具数"
                    value={stats.total_tools}
                    prefix={<ToolOutlined />}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card className="stat-card valid">
                  <Statistic
                    title="有效工具"
                    value={stats.valid_tools}
                    prefix={<CheckCircleOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card className="stat-card invalid">
                  <Statistic
                    title="无效工具"
                    value={stats.invalid_tools}
                    prefix={<CloseCircleOutlined />}
                    valueStyle={{ color: '#ff4d4f' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card className="stat-card calls">
                  <Statistic
                    title="总调用次数"
                    value={stats.total_calls}
                    prefix={<ThunderboltOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
            </Row>

            <Row gutter={[24, 24]} className="stats-charts">
              <Col xs={24} md={12}>
                <Card title="工具状态分布" className="chart-card">
                  <div className="status-distribution">
                    <div className="status-item">
                      <span className="status-label">有效</span>
                      <Progress
                        percent={tools.length ? (statusCounts.valid / tools.length) * 100 : 0}
                        strokeColor="#52c41a"
                        format={() => statusCounts.valid}
                      />
                    </div>
                    <div className="status-item">
                      <span className="status-label">无效</span>
                      <Progress
                        percent={tools.length ? (statusCounts.invalid / tools.length) * 100 : 0}
                        strokeColor="#ff4d4f"
                        format={() => statusCounts.invalid}
                      />
                    </div>
                    <div className="status-item">
                      <span className="status-label">待验证</span>
                      <Progress
                        percent={tools.length ? (statusCounts.pending / tools.length) * 100 : 0}
                        strokeColor="#faad14"
                        format={() => statusCounts.pending}
                      />
                    </div>
                    <div className="status-item">
                      <span className="status-label">已禁用</span>
                      <Progress
                        percent={tools.length ? (statusCounts.disabled / tools.length) * 100 : 0}
                        strokeColor="#8c8c8c"
                        format={() => statusCounts.disabled}
                      />
                    </div>
                  </div>
                </Card>
              </Col>

              <Col xs={24} md={12}>
                <Card title="工具调用排行" className="chart-card">
                  {topTools.length > 0 && topTools.some(t => t.call_count > 0) ? (
                    <div className="call-ranking">
                      {topTools.map((tool, index) => (
                        <div key={tool.id} className="ranking-item">
                          <span className="ranking-number">{index + 1}</span>
                          <span className="ranking-name">{tool.name}</span>
                          <div className="ranking-bar-container">
                            <div
                              className="ranking-bar"
                              style={{
                                width: `${(tool.call_count / maxCalls) * 100}%`,
                              }}
                            />
                          </div>
                          <span className="ranking-count">{tool.call_count}</span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty description="暂无调用数据" />
                  )}
                </Card>
              </Col>
            </Row>
          </>
        )}
      </Spin>
    </div>
  );
}

export default Statistics;
