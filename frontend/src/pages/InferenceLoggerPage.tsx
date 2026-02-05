import { useState, useEffect } from 'react';
import { Search, Filter, RefreshCw, Eye, Clock, CheckCircle, XCircle } from 'lucide-react';
import { logsAPI } from '../services/api';
import type { InferenceLog } from '../types/api';
import './InferenceLoggerPage.css';

const InferenceLoggerPage = () => {
  const [logs, setLogs] = useState<InferenceLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLog, setSelectedLog] = useState<InferenceLog | null>(null);
  const [filters, setFilters] = useState({
    statusCode: '',
    path: '',
    method: '',
  });
  const [pagination, setPagination] = useState({
    limit: 50,
    offset: 0,
    total: 0,
  });

  useEffect(() => {
    loadLogs();
  }, [pagination.offset, pagination.limit, filters]);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await logsAPI.getLogs(pagination.limit, pagination.offset);
      setLogs(response.logs || []);
      setPagination((prev) => ({ ...prev, total: response.total }));
    } catch (error: any) {
      console.error('Failed to load logs:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to load inference logs');
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPagination((prev) => ({ ...prev, offset: 0 }));
  };

  const clearFilters = () => {
    setFilters({ statusCode: '', path: '', method: '' });
    setPagination((prev) => ({ ...prev, offset: 0 }));
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 0.001) return `${(seconds * 1000000).toFixed(0)}μs`;
    if (seconds < 1) return `${(seconds * 1000).toFixed(2)}ms`;
    return `${seconds.toFixed(2)}s`;
  };

  const getStatusIcon = (statusCode: number) => {
    if (statusCode >= 200 && statusCode < 300) {
      return <CheckCircle size={16} className="status-icon success" />;
    }
    if (statusCode >= 400) {
      return <XCircle size={16} className="status-icon error" />;
    }
    return <Clock size={16} className="status-icon warning" />;
  };

  const filteredLogs = logs.filter((log) => {
    if (filters.statusCode && log.status_code !== Number(filters.statusCode)) return false;
    if (filters.path && !log.path.toLowerCase().includes(filters.path.toLowerCase())) return false;
    if (filters.method && log.method.toUpperCase() !== filters.method.toUpperCase()) return false;
    return true;
  });

  return (
    <div className="inference-logger-page">
      <div className="page-header">
        <div>
          <h1>Inference Logger</h1>
          <p>View and monitor all API inference requests and responses</p>
        </div>
        <button className="refresh-button" onClick={loadLogs} disabled={loading}>
          <RefreshCw size={18} className={loading ? 'spinning' : ''} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <p>{error}</p>
          <button onClick={loadLogs}>Retry</button>
        </div>
      )}

      <div className="filters-section">
        <div className="filter-group">
          <label>Status Code</label>
          <input
            type="text"
            placeholder="e.g., 200"
            value={filters.statusCode}
            onChange={(e) => handleFilterChange('statusCode', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label>Path</label>
          <input
            type="text"
            placeholder="e.g., /api/v1/chat"
            value={filters.path}
            onChange={(e) => handleFilterChange('path', e.target.value)}
          />
        </div>
        <div className="filter-group">
          <label>Method</label>
          <select
            value={filters.method}
            onChange={(e) => handleFilterChange('method', e.target.value)}
          >
            <option value="">All</option>
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>
        <button className="clear-filters-button" onClick={clearFilters}>
          Clear Filters
        </button>
      </div>

      <div className="logs-container">
        <div className="logs-list">
          {loading ? (
            <div className="loading-state">Loading logs...</div>
          ) : filteredLogs.length === 0 ? (
            <div className="empty-state">
              <p>No inference logs found</p>
            </div>
          ) : (
            <>
              <div className="logs-table-header">
                <div className="table-header-cell">Timestamp</div>
                <div className="table-header-cell">Method</div>
                <div className="table-header-cell">Path</div>
                <div className="table-header-cell">Status</div>
                <div className="table-header-cell">Duration</div>
                <div className="table-header-cell">Actions</div>
              </div>
              {filteredLogs.map((log) => (
                <div
                  key={log.id}
                  className={`log-row ${selectedLog?.id === log.id ? 'selected' : ''}`}
                  onClick={() => setSelectedLog(log)}
                >
                  <div className="log-cell timestamp">
                    {new Date(log.timestamp).toLocaleString()}
                  </div>
                  <div className="log-cell method">{log.method}</div>
                  <div className="log-cell path">{log.path}</div>
                  <div className="log-cell status">
                    {getStatusIcon(log.status_code)}
                    <span>{log.status_code}</span>
                  </div>
                  <div className="log-cell duration">{formatDuration(log.duration)}</div>
                  <div className="log-cell actions">
                    <button
                      className="view-button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedLog(log);
                      }}
                    >
                      <Eye size={16} />
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {selectedLog && (
          <div className="log-details-panel">
            <div className="details-header">
              <h2>Log Details</h2>
              <button className="close-button" onClick={() => setSelectedLog(null)}>
                ×
              </button>
            </div>
            <div className="details-content">
              <div className="detail-section">
                <h3>Request Information</h3>
                <div className="detail-item">
                  <span className="detail-label">Request ID:</span>
                  <span className="detail-value">{selectedLog.request_id}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Timestamp:</span>
                  <span className="detail-value">
                    {new Date(selectedLog.timestamp).toLocaleString()}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Method:</span>
                  <span className="detail-value">{selectedLog.method}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Path:</span>
                  <span className="detail-value">{selectedLog.path}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Status Code:</span>
                  <span
                    className={`detail-value ${
                      selectedLog.status_code >= 200 && selectedLog.status_code < 300
                        ? 'success'
                        : selectedLog.status_code >= 400
                        ? 'error'
                        : ''
                    }`}
                  >
                    {selectedLog.status_code}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Duration:</span>
                  <span className="detail-value">{formatDuration(selectedLog.duration)}</span>
                </div>
                {selectedLog.error && (
                  <div className="detail-item">
                    <span className="detail-label">Error:</span>
                    <span className="detail-value error">{selectedLog.error}</span>
                  </div>
                )}
              </div>

              {selectedLog.metadata && (
                <div className="detail-section">
                  <h3>Metadata</h3>
                  <pre className="metadata-content">
                    {JSON.stringify(selectedLog.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {!loading && filteredLogs.length > 0 && (
        <div className="pagination">
          <button
            disabled={pagination.offset === 0}
            onClick={() => setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))}
          >
            Previous
          </button>
          <span>
            Showing {pagination.offset + 1} - {Math.min(pagination.offset + pagination.limit, pagination.total)} of{' '}
            {pagination.total}
          </span>
          <button
            disabled={pagination.offset + pagination.limit >= pagination.total}
            onClick={() =>
              setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
            }
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default InferenceLoggerPage;
