import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 获取工具列表
export const getTools = async (params = {}) => {
  const response = await api.get('/tools/', { params });
  return response.data;
};

// 获取工具详情
export const getTool = async (id) => {
  const response = await api.get(`/tools/${id}`);
  return response.data;
};

// 创建工具
export const createTool = async (data) => {
  const response = await api.post('/tools/', data);
  return response.data;
};

// 删除工具
export const deleteTool = async (id) => {
  const response = await api.delete(`/tools/${id}`);
  return response.data;
};

// 验证工具
export const validateTool = async (sourceCode) => {
  const response = await api.post('/tools/validate', null, {
    params: { source_code: sourceCode }
  });
  return response.data;
};

// 获取统计信息
export const getStatistics = async () => {
  const response = await api.get('/tools/statistics');
  return response.data;
};

// 获取规范文档
export const getSpec = async () => {
  const response = await api.get('/tools/spec');
  return response.data;
};

// 执行工具
export const executeTool = async (data) => {
  const response = await api.post('/mcp/call', data);
  return response.data;
};

export default api;
