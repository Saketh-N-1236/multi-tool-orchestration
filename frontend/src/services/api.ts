import axios from 'axios';
import type {
  ChatRequest,
  ChatResponse,
  InferenceLog,
  OverviewStats,
  ToolUsageStats,
  DocumentUploadRequest,
  DocumentUploadResponse,
  Tool,
  HealthResponse,
} from '../types/api';

const API_BASE = '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 2 minutes timeout for chat requests
});

// Chat API
export const chatAPI = {
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    // Use longer timeout for chat requests (agent execution can take time)
    const response = await api.post<ChatResponse>('/chat', request, {
      timeout: 180000, // 3 minutes for agent execution
    });
    return response.data;
  },
};

// Analytics API
export const analyticsAPI = {
  getOverview: async (): Promise<OverviewStats> => {
    const response = await api.get<OverviewStats>('/analytics/overview');
    return response.data;
  },
  getTools: async (): Promise<{ tools: ToolUsageStats[] }> => {
    const response = await api.get<{ tools: ToolUsageStats[] }>('/analytics/tools');
    return response.data;
  },
  getResponseTimes: async (timeWindowHours?: number): Promise<any> => {
    const params = timeWindowHours ? { time_window_hours: timeWindowHours } : {};
    const response = await api.get('/analytics/response-times', { params });
    return response.data;
  },
  getTimeSeries: async (timeWindowHours: number = 24, intervalMinutes: number = 60): Promise<any> => {
    const response = await api.get('/analytics/time-series', {
      params: { time_window_hours: timeWindowHours, interval_minutes: intervalMinutes },
    });
    return response.data;
  },
  getErrors: async (): Promise<any> => {
    const response = await api.get('/analytics/errors');
    return response.data;
  },
};

// Documents API
export const documentsAPI = {
  upload: async (request: DocumentUploadRequest): Promise<DocumentUploadResponse> => {
    const response = await api.post<DocumentUploadResponse>('/documents/upload', request);
    return response.data;
  },
  uploadFile: async (file: File, collection: string): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<DocumentUploadResponse>('/documents/upload-file', formData, {
      params: { collection },
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
  getCollections: async (): Promise<{ collections: string[] }> => {
    const response = await api.get<{ collections: string[] }>('/documents/collections');
    return response.data;
  },
  deleteCollection: async (collectionName: string): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/documents/collections/${encodeURIComponent(collectionName)}`);
    return response.data;
  },
};

// Tools API
export const toolsAPI = {
  list: async (): Promise<{ tools: Tool[]; count: number }> => {
    const response = await api.get<{ tools: Tool[]; count: number }>('/tools');
    return response.data;
  },
};

// Health API
export const healthAPI = {
  check: async (): Promise<HealthResponse> => {
    const response = await api.get<HealthResponse>('/health');
    return response.data;
  },
  status: async (): Promise<any> => {
    const response = await api.get('/status');
    return response.data;
  },
};

// Logs API
export const logsAPI = {
  getLogs: async (limit: number = 100, offset: number = 0): Promise<{
    logs: InferenceLog[];
    total: number;
    limit: number;
    offset: number;
  }> => {
    const response = await api.get('/logs', {
      params: { limit, offset },
    });
    return response.data;
  },
  getLog: async (requestId: string): Promise<InferenceLog> => {
    const response = await api.get<InferenceLog>(`/logs/${requestId}`);
    return response.data;
  },
};

// MLflow API
export const mlflowAPI = {
  getExperiment: async (limit: number = 50): Promise<any> => {
    const response = await api.get('/mlflow/experiment', {
      params: { limit },
    });
    return response.data;
  },
};

// CRUD API
export const crudAPI = {
  // Database operations
  createDatabase: async (name: string, type: string = 'sqlite'): Promise<any> => {
    const response = await api.post('/databases', { name, type });
    return response.data;
  },
  listDatabases: async (): Promise<any[]> => {
    const response = await api.get('/databases');
    return response.data;
  },
  getDatabase: async (name: string): Promise<any> => {
    const response = await api.get(`/databases/${encodeURIComponent(name)}`);
    return response.data;
  },
  deleteDatabase: async (name: string): Promise<any> => {
    const response = await api.delete(`/databases/${encodeURIComponent(name)}`);
    return response.data;
  },

  // Table operations
  createTable: async (databaseName: string, tableName: string, columns: any[]): Promise<any> => {
    const response = await api.post(`/databases/${encodeURIComponent(databaseName)}/tables`, {
      table_name: tableName,
      columns,
    });
    return response.data;
  },
  listTables: async (databaseName: string): Promise<any[]> => {
    const response = await api.get(`/databases/${encodeURIComponent(databaseName)}/tables`);
    return response.data;
  },
  getTable: async (databaseName: string, tableName: string): Promise<any> => {
    const response = await api.get(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}`
    );
    return response.data;
  },
  deleteTable: async (databaseName: string, tableName: string): Promise<any> => {
    const response = await api.delete(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}`
    );
    return response.data;
  },

  // Row operations
  insertRow: async (databaseName: string, tableName: string, data: Record<string, any>): Promise<any> => {
    const response = await api.post(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}/rows`,
      { data }
    );
    return response.data;
  },
  listRows: async (
    databaseName: string,
    tableName: string,
    limit: number = 100,
    offset: number = 0,
    where?: string
  ): Promise<any> => {
    const params: any = { limit, offset };
    if (where) params.where = where;
    const response = await api.get(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}/rows`,
      { params }
    );
    return response.data;
  },
  getRow: async (databaseName: string, tableName: string, rowId: number): Promise<any> => {
    const response = await api.get(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}/rows/${rowId}`
    );
    return response.data;
  },
  updateRow: async (
    databaseName: string,
    tableName: string,
    rowId: number,
    data: Record<string, any>
  ): Promise<any> => {
    const response = await api.put(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}/rows/${rowId}`,
      { data }
    );
    return response.data;
  },
  deleteRow: async (databaseName: string, tableName: string, rowId: number): Promise<any> => {
    const response = await api.delete(
      `/databases/${encodeURIComponent(databaseName)}/tables/${encodeURIComponent(tableName)}/rows/${rowId}`
    );
    return response.data;
  },
};

export default api;
