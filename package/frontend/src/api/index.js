import axios from 'axios';

// API 基础路径配置
// 开发环境和生产环境都使用 /api 前缀
// 后端路由在 main.py 中以 /api 为前缀注册
const getBaseURL = () => {
  return '/api';
};

const api = axios.create({
  baseURL: getBaseURL(),
  timeout: 30000, // 默认30秒超时，各端点可单独覆盖
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const cardKey = localStorage.getItem('cardKey');
    if (cardKey) {
      config.headers['X-Card-Key'] = cardKey;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('cardKey');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

// Admin API
export const adminAPI = {
  generateKeys: (data, token) =>
    api.post('/admin/generate-keys', data, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  listUsers: (token) =>
    api.get('/admin/users', {
      headers: { Authorization: `Bearer ${token}` },
    }),
  deleteUser: (userId, token) =>
    api.delete(`/admin/users/${userId}`, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  stopSession: (sessionId, token) =>
    api.post(`/admin/sessions/${sessionId}/stop`, null, {
      headers: { Authorization: `Bearer ${token}` },
    }),
  toggleUserActive: (userId, token) =>
    api.patch(`/admin/users/${userId}/toggle`, null, {
      headers: { Authorization: `Bearer ${token}` },
    }),
};

// Prompts API
export const promptsAPI = {
  getSystemPrompts: () => api.get('/prompts/system'),
  getUserPrompts: (stage = null) =>
    api.get('/prompts/', {
      params: stage ? { stage } : {},
    }),
  createPrompt: (data) => api.post('/prompts/', data),
  updatePrompt: (promptId, data) => api.put(`/prompts/${promptId}`, data),
  deletePrompt: (promptId) => api.delete(`/prompts/${promptId}`),
  setDefaultPrompt: (promptId) =>
    api.post(`/prompts/${promptId}/set-default`),
};

// Optimization API
export const optimizationAPI = {
  startOptimization: (data) => api.post('/optimization/start', data, {
    timeout: 60000, // 启动任务延长到60秒超时
  }),
  startFileOptimization: (file, processingMode) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('processing_mode', processingMode);
    return api.post('/optimization/start-file', formData, {
      timeout: 120000,
    });
  },
  getQueueStatus: (sessionId = null) =>
    api.get('/optimization/status', {
      params: sessionId ? { session_id: sessionId } : {},
      timeout: 10000, // 10秒超时
    }),
  listSessions: () => api.get('/optimization/sessions', {
    timeout: 15000, // 15秒超时
  }),
  getSessionDetail: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}`, {
      timeout: 20000, // 20秒超时
    }),
  getSessionProgress: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}/progress`, {
      timeout: 10000, // 10秒超时
    }),
  getSessionChanges: (sessionId) =>
    api.get(`/optimization/sessions/${sessionId}/changes`, {
      timeout: 20000, // 20秒超时
    }),
  stopSession: (sessionId) =>
    api.post(`/optimization/sessions/${sessionId}/stop`, null, {
      timeout: 10000, // 10秒超时
    }),
  exportSession: (sessionId, confirmation) =>
    api.post(`/optimization/sessions/${sessionId}/export`, confirmation, {
      timeout: 30000, // 30秒超时
      responseType: 'blob',
    }),
  deleteSession: (sessionId) =>
    api.delete(`/optimization/sessions/${sessionId}`, {
      timeout: 10000, // 10秒超时
    }),
  resumeSession: (sessionId) =>
    api.post(`/optimization/sessions/${sessionId}/retry`, null, {
      timeout: 15000, // 15秒超时
    }),
  getStreamUrl: (sessionId) => {
    const baseUrl = api.defaults.baseURL || '/api';
    return `${baseUrl}/optimization/sessions/${sessionId}/stream`;
  },
};

// Health API
export const healthAPI = {
  checkModels: () => api.get('/health/models', {
    timeout: 15000, // 15秒超时
  }),
};

// Word Formatter API
export const wordFormatterAPI = {
  // Usage info (shared with polishing)
  getUsage: () => api.get('/word-formatter/usage'),

  // Built-in Specs
  listSpecs: () => api.get('/word-formatter/specs'),
  getSpecSchema: () => api.get('/word-formatter/specs/schema'),
  validateSpec: (specJson) =>
    api.post('/word-formatter/specs/validate', null, {
      params: { spec_json: specJson },
    }),
  generateSpec: (requirements) =>
    api.post('/word-formatter/specs/generate', { requirements }, {
      timeout: 120000, // AI generation may take time
    }),

  // Saved Specs (user's custom specs)
  saveSpec: (name, specJson, description = null) =>
    api.post('/word-formatter/specs/save', {
      name,
      spec_json: specJson,
      description,
    }),
  listSavedSpecs: () => api.get('/word-formatter/specs/saved'),
  getSavedSpec: (specId) => api.get(`/word-formatter/specs/saved/${specId}`),
  deleteSavedSpec: (specId) => api.delete(`/word-formatter/specs/saved/${specId}`),

  // Format text
  formatText: (data) =>
    api.post('/word-formatter/format/text', data, {
      timeout: 60000,
    }),

  // Format file
  formatFile: (file, options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    const customSpecJson = options.custom_spec_json || options.spec_json;
    if (customSpecJson) {
      formData.append('custom_spec_json', customSpecJson);
    }
    const { custom_spec_json, spec_json, ...queryOptions } = options;
    return api.post('/word-formatter/format/file', formData, {
      params: queryOptions,
      timeout: 120000,
    });
  },

  // Jobs
  getJobStatus: (jobId) => api.get(`/word-formatter/jobs/${jobId}`),
  listJobs: (limit = 10) =>
    api.get('/word-formatter/jobs', { params: { limit } }),
  deleteJob: (jobId) => api.delete(`/word-formatter/jobs/${jobId}`),
  getJobReport: (jobId) => api.get(`/word-formatter/jobs/${jobId}/report`),
  downloadJob: (jobId) => api.get(`/word-formatter/jobs/${jobId}/download`, {
    responseType: 'blob',
    timeout: 120000,
  }),

  // SSE stream URL
  getStreamUrl: (jobId) => {
    const baseUrl = api.defaults.baseURL || '/api';
    return `${baseUrl}/word-formatter/jobs/${jobId}/stream`;
  },

  // Preprocess text
  preprocessText: (text, options = {}) =>
    api.post('/word-formatter/preprocess/text', {
      text,
      chunk_paragraphs: options.chunkParagraphs || 40,
      chunk_chars: options.chunkChars || 8000,
    }, {
      timeout: 60000,
    }),

  // Preprocess file
  preprocessFile: (file, options = {}) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/word-formatter/preprocess/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: {
        chunk_paragraphs: options.chunkParagraphs || 40,
        chunk_chars: options.chunkChars || 8000,
      },
      timeout: 120000,
    });
  },

  // Preprocess stream URL
  getPreprocessStreamUrl: (jobId) => {
    const baseUrl = api.defaults.baseURL || '/api';
    return `${baseUrl}/word-formatter/preprocess/${jobId}/stream`;
  },

  // Get preprocess result
  getPreprocessResult: (jobId) =>
    api.get(`/word-formatter/preprocess/${jobId}/result`),

  // Delete preprocess job
  deletePreprocessJob: (jobId) =>
    api.delete(`/word-formatter/preprocess/${jobId}`),

  // ============ Format Check API (No AI Required) ============

  // Get paragraph types
  getFormatParagraphTypes: () =>
    api.get('/word-formatter/format-check/types'),

  // Check text format (synchronous)
  checkTextFormat: (text, mode = 'loose') =>
    api.post('/word-formatter/format-check/text', { text, mode }, {
      timeout: 30000,
    }),

  // Check file format (synchronous)
  checkFileFormat: (file, mode = 'loose') => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/word-formatter/format-check/file', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: { mode },
      timeout: 60000,
    });
  },
};

export default api;
