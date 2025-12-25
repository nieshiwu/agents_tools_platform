import React, { useState, useEffect } from 'react';
import { Input, Select, Row, Col, Empty, Spin, message, Modal, Tag, Button, Space } from 'antd';
import { SearchOutlined, ReloadOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons';
import ToolCard from './ToolCard';
import ToolDetail from './ToolDetail';
import { getTools, deleteTool } from '../api';
import './ToolList.css';

const { Search } = Input;
const { Option } = Select;

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'valid', label: '有效' },
  { value: 'invalid', label: '无效' },
  { value: 'pending', label: '待验证' },
  { value: 'disabled', label: '已禁用' },
];

function ToolList() {
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedTool, setSelectedTool] = useState(null);
  const [detailVisible, setDetailVisible] = useState(false);

  const fetchTools = async () => {
    setLoading(true);
    try {
      const params = {};
      if (searchText) params.search = searchText;
      if (statusFilter) params.status = statusFilter;
      const data = await getTools(params);
      setTools(data);
    } catch (error) {
      message.error('获取工具列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTools();
  }, [statusFilter]);

  const handleSearch = (value) => {
    setSearchText(value);
    fetchTools();
  };

  const handleDelete = async (id, name) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除工具 "${name}" 吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await deleteTool(id);
          message.success('删除成功');
          fetchTools();
        } catch (error) {
          message.error('删除失败');
        }
      },
    });
  };

  const handleViewDetail = (tool) => {
    setSelectedTool(tool);
    setDetailVisible(true);
  };

  return (
    <div className="tool-list-container">
      <div className="tool-list-header">
        <h2>工具列表</h2>
        <div className="tool-list-filters">
          <Space size="middle">
            <Search
              placeholder="搜索工具名称或描述..."
              allowClear
              enterButton={<SearchOutlined />}
              onSearch={handleSearch}
              style={{ width: 300 }}
            />
            <Select
              value={statusFilter}
              onChange={setStatusFilter}
              style={{ width: 120 }}
            >
              {statusOptions.map((opt) => (
                <Option key={opt.value} value={opt.value}>
                  {opt.label}
                </Option>
              ))}
            </Select>
            <Button icon={<ReloadOutlined />} onClick={fetchTools}>
              刷新
            </Button>
          </Space>
        </div>
      </div>

      <Spin spinning={loading}>
        {tools.length === 0 ? (
          <Empty
            description="暂无工具，点击「上传工具」添加新工具"
            className="empty-state"
          />
        ) : (
          <div className="tool-grid">
            {tools.map((tool) => (
              <ToolCard
                key={tool.id}
                tool={tool}
                onView={() => handleViewDetail(tool)}
                onDelete={() => handleDelete(tool.id, tool.name)}
              />
            ))}
          </div>
        )}
      </Spin>

      <ToolDetail
        visible={detailVisible}
        tool={selectedTool}
        onClose={() => setDetailVisible(false)}
      />
    </div>
  );
}

export default ToolList;
