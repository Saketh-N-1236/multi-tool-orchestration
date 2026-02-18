export interface ChatRequest {
  message: string;
  session_id?: string;
  max_iterations?: number;
  temperature?: number;
  max_tokens?: number;
}

export interface ToolCall {
  tool_name: string;
  params: Record<string, any>;
  timestamp: string;
  step: number;
}

export interface ToolResult {
  tool_name: string;
  result: any;
  error: string | null;
  timestamp: string;
  step: number;
}

export interface ChatResponse {
  response: string;
  request_id: string;
  session_id?: string;
  tool_calls: ToolCall[];
  tool_results: ToolResult[];
  iterations: number;
  metadata: Record<string, any>;
}

export interface InferenceLog {
  id: number;
  request_id: string;
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  duration: number;
  error: string | null;
  question: string | null;
  answer: string | null;
  metadata: Record<string, any>;
}

export interface OverviewStats {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  average_response_time: number;
  total_tool_calls: number;
  unique_tools_used: number;
  status_distribution: Record<string, number>;
  path_distribution: Record<string, number>;
}

export interface ToolUsageStats {
  tool_name: string;
  call_count: number;
  success_count: number;
  failure_count: number;
  average_duration: number;
}

export interface DocumentUploadRequest {
  documents: Array<{
    id: string;
    text: string;
    metadata?: Record<string, any>;
  }>;
  collection: string;
}

export interface DocumentUploadResponse {
  success: boolean;
  message: string;
  document_ids: string[];
  collection: string;
}

export interface ToolParameter {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: any;
}

export interface Tool {
  name: string;
  description: string;
  server: string;
  version: string;
  parameters?: ToolParameter[];
  expected_output?: {
    type: string;
    description: string;
  };
}

export interface HealthResponse {
  status: string;
  version: string;
  llm_provider: string;
  mcp_servers: Record<string, string>;
}

// CRUD Types
export interface Database {
  name: string;
  type: string;
  table_count: number;
  schema_count: number;
}

export interface Table {
  name: string;
  column_count: number;
  row_count: number;
}

export interface TableSchema {
  table_name: string;
  catalog: string;
  schema: string;
  columns: Array<{
    name: string;
    type: string;
    not_null: boolean;
    default_value: any;
    primary_key: boolean;
  }>;
  row_count: number;
}

export interface ColumnDefinition {
  name: string;
  type: string;
  primary_key?: boolean;
  not_null?: boolean;
  default?: any;
}

export interface CreateDatabaseRequest {
  name: string;
  type: string;
}

export interface CreateTableRequest {
  table_name: string;
  columns: ColumnDefinition[];
}

export interface Row {
  [key: string]: any;
  rowid?: number;
}

export interface RowListResponse {
  database: string;
  table: string;
  rows: Row[];
  count: number;
  total: number;
  limit: number;
  offset: number;
}
