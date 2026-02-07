import axios from 'axios';
import type { Student, Conversation, Rule, WeeklyPrompt, DashboardStats } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || '';

function getAppBasePath(): string {
  // Prefer Vite-provided base when available.
  const viteBase = import.meta.env.BASE_URL || '/';
  if (viteBase && viteBase !== '/') {
    return viteBase.endsWith('/') ? viteBase : `${viteBase}/`;
  }

  // Fallback: derive from current pathname (useful behind reverse proxies).
  const pathname = window.location?.pathname || '/';
  if (pathname === '/TeachProxy' || pathname.startsWith('/TeachProxy/')) {
    return '/TeachProxy/';
  }
  return '/';
}

const api = axios.create({
  baseURL: `${API_BASE}/admin`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token');
      window.location.href = `${getAppBasePath()}login`;
    }
    return Promise.reject(error);
  }
);

// Dashboard API
export const dashboardApi = {
  getStats: () => api.get<DashboardStats>('/dashboard/stats').then(r => r.data),
  getActivity: (days = 7) => api.get('/dashboard/activity', { params: { days } }).then(r => r.data),
};

// Students API
export const studentsApi = {
  list: () => api.get<Student[]>('/students').then(r => r.data),
  create: (data: { name: string; email: string; quota: number }) =>
    api.post('/students', data).then(r => r.data),
  updateQuota: (id: string, quota: number) =>
    api.put(`/students/${id}/quota`, { quota }).then(r => r.data),
  resetQuota: (id: string) =>
    api.post(`/students/${id}/reset-quota`).then(r => r.data),
  regenerateKey: (id: string) =>
    api.post(`/students/${id}/regenerate-key`).then(r => r.data),
  delete: (id: string) =>
    api.delete(`/students/${id}`).then(r => r.data),
  getStats: (id: string) =>
    api.get(`/students/${id}/stats`).then(r => r.data),
};

// Conversations API
export const conversationsApi = {
  list: (params?: { limit?: number; offset?: number; student_id?: string; action?: string; search?: string }) =>
    api.get<{ items: Conversation[]; total: number }>('/conversations', { params }).then(r => r.data),
  
  getByStudent: (studentId: string, params?: { limit?: number; offset?: number }) =>
    api.get<{ items: Conversation[]; total: number }>(`/conversations/student/${studentId}`, { params }).then(r => r.data),
  
  search: (query: string, params?: { limit?: number; offset?: number }) =>
    api.get<{ items: Conversation[]; total: number; query: string }>('/conversations/search', { params: { q: query, ...params } }).then(r => r.data),
};

// Rules API
export const rulesApi = {
  list: () => api.get<Rule[]>('/rules').then(r => r.data),
  create: (data: Omit<Rule, 'id'>) => api.post('/rules', data).then(r => r.data),
  update: (id: number, data: Partial<Rule>) => api.put(`/rules/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/rules/${id}`).then(r => r.data),
  toggle: (id: number) => api.post(`/rules/${id}/toggle`).then(r => r.data),
  reloadCache: () => api.post('/rules/reload-cache').then(r => r.data),
};

// Weekly Prompts API
export const promptsApi = {
  list: () => api.get<WeeklyPrompt[]>('/weekly-prompts').then(r => r.data),
  getCurrent: () => api.get<WeeklyPrompt | null>('/weekly-prompts/current').then(r => r.data),
  create: (data: Omit<WeeklyPrompt, 'id'>) => api.post('/weekly-prompts', data).then(r => r.data),
  delete: (id: number) => api.delete(`/weekly-prompts/${id}`).then(r => r.data),
};

export default api;
