import { useState, useEffect } from 'react';
import { ExternalLink, RefreshCw, Database, Activity, TrendingUp, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { healthAPI, mlflowAPI } from '../services/api';
import './MLLoggerPage.css';

interface MLflowRun {
  run_id: string;
  run_name: string;
  status: string;
  start_time: number;
  end_time?: number;
  request_id?: string;
  prompt_version?: string;
  model_name?: string;
  metrics: Record<string, number>;
  params: Record<string, string>;
}

interface MLflowExperiment {
  experiment_id: string;
  experiment_name: string;
  artifact_location: string;
  lifecycle_stage: string;
  run_count: number;
  runs: MLflowRun[];
}

const MLLoggerPage = () => {
  const [mlflowUri, setMlflowUri] = useState<string>('http://localhost:5000');
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [experiment, setExperiment] = useState<MLflowExperiment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRun, setSelectedRun] = useState<MLflowRun | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await healthAPI.status();
      setHealthStatus(status);
      if (status.features?.mlflow_tracking_uri) {
        setMlflowUri(status.features.mlflow_tracking_uri);
      }
      
      // Check if MLflow is enabled before trying to fetch experiment data
      if (!status.features?.mlflow_tracking) {
        setError(
          'MLflow tracking is disabled. To enable MLflow:\n' +
          '1. Install MLflow: pip install mlflow\n' +
          '2. Start MLflow server: mlflow ui --port 5000\n' +
          '3. Configure MLflow tracking URI in your settings'
        );
        setExperiment(null);
        setLoading(false);
        return;
      }
      
      // Try to fetch experiment data
      try {
        const experimentData = await mlflowAPI.getExperiment(50);
        setExperiment(experimentData);
      } catch (experimentError: any) {
        // Handle 503 or other MLflow errors
        if (experimentError.response?.status === 503) {
          setError(
            'MLflow tracking is not available. ' +
            (experimentError.response?.data?.detail || 
             'Please ensure MLflow is installed and the tracking server is running.')
          );
        } else {
          setError(experimentError.response?.data?.detail || experimentError.message || 'Failed to load experiment data');
        }
        setExperiment(null);
      }
    } catch (error: any) {
      console.error('Failed to load data:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to load MLflow data');
      setExperiment(null);
    } finally {
      setLoading(false);
    }
  };

  const loadHealthStatus = async () => {
    await loadData();
  };

  const openMLflowUI = () => {
    window.open(mlflowUri, '_blank');
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp / 1000).toLocaleString();
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'finished':
        return <CheckCircle size={16} className="status-icon success" />;
      case 'failed':
        return <XCircle size={16} className="status-icon error" />;
      case 'running':
        return <Clock size={16} className="status-icon running" />;
      default:
        return <AlertCircle size={16} className="status-icon warning" />;
    }
  };

  const formatDuration = (startTime: number, endTime?: number) => {
    if (!endTime) return 'Running...';
    const duration = (endTime - startTime) / 1000;
    if (duration < 1) return `${(duration * 1000).toFixed(0)}ms`;
    if (duration < 60) return `${duration.toFixed(1)}s`;
    return `${(duration / 60).toFixed(1)}m`;
  };

  return (
    <div className="ml-logger-page">
      <div className="page-header">
        <div>
          <h1>MLflow Logger</h1>
          <p>Track and monitor MLflow experiments and model performance</p>
        </div>
        <button className="refresh-button" onClick={loadHealthStatus} disabled={loading}>
          <RefreshCw size={18} className={loading ? 'spinning' : ''} />
          Refresh
        </button>
      </div>

      <div className="mlflow-info-cards">
        <div className="info-card">
          <div className="info-card-header">
            <Database size={24} />
            <h3>MLflow Tracking</h3>
          </div>
          <div className="info-card-content">
            <p className="info-description">
              MLflow is used to track experiments, log parameters, metrics, and artifacts for the agent system.
            </p>
            <div className="info-details">
              <div className="info-item">
                <span className="info-label">Tracking URI:</span>
                <span className="info-value">{mlflowUri}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Experiment Name:</span>
                <span className="info-value">
                  {experiment?.experiment_name || healthStatus?.features?.mlflow_experiment_name || 'mcp_agent_experiments'}
                </span>
              </div>
            </div>
            <button className="open-mlflow-button" onClick={openMLflowUI}>
              <ExternalLink size={18} />
              Open MLflow UI
            </button>
          </div>
        </div>

        <div className="info-card">
          <div className="info-card-header">
            <Activity size={24} />
            <h3>What's Tracked</h3>
          </div>
          <div className="info-card-content">
            <ul className="tracked-items">
              <li>
                <strong>Prompt Versions:</strong> Track different prompt versions used in experiments
              </li>
              <li>
                <strong>Model Names:</strong> Record which LLM models are being used
              </li>
              <li>
                <strong>Request IDs:</strong> Correlate MLflow runs with inference logs
              </li>
              <li>
                <strong>Agent Metrics:</strong> Track execution time, iterations, and tool usage
              </li>
              <li>
                <strong>Tool Statistics:</strong> Monitor tool call counts and success rates
              </li>
              <li>
                <strong>Evaluation Results:</strong> AI judge scores for correctness, relevance, completeness
              </li>
            </ul>
          </div>
        </div>

        <div className="info-card">
          <div className="info-card-header">
            <TrendingUp size={24} />
            <h3>Usage</h3>
          </div>
          <div className="info-card-content">
            <div className="usage-steps">
              <div className="step">
                <div className="step-number">1</div>
                <div className="step-content">
                  <h4>Start MLflow Server</h4>
                  <p>Run: <code>mlflow ui --port 5000</code></p>
                </div>
              </div>
              <div className="step">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h4>Run Agent Evaluation</h4>
                  <p>Execute: <code>python backend/scripts/evaluate_agent.py</code></p>
                </div>
              </div>
              <div className="step">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h4>View Results</h4>
                  <p>Open MLflow UI to see experiment runs and compare results</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Experiment Results Section */}
      <div className="experiment-results-section">
        <div className="section-header">
          <h2>Experiment Results</h2>
          <button className="refresh-button-small" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spinning' : ''} />
            Refresh
          </button>
        </div>

        {error && !experiment && (
          <div className="error-banner">
            <div className="error-content">
              <AlertCircle size={20} className="error-icon" />
              <div className="error-text">
                <p className="error-title">MLflow Tracking Unavailable</p>
                <p className="error-message">{error}</p>
              </div>
            </div>
            <button onClick={loadData} className="retry-button">Retry</button>
          </div>
        )}

        {loading && !experiment && !error ? (
          <div className="loading-state">Loading experiment data...</div>
        ) : experiment && experiment.runs.length > 0 ? (
          <div className="runs-container">
            <div className="runs-list">
              <div className="runs-table-header">
                <div className="table-header-cell">Run Name</div>
                <div className="table-header-cell">Status</div>
                <div className="table-header-cell">Model</div>
                <div className="table-header-cell">Start Time</div>
                <div className="table-header-cell">Duration</div>
                <div className="table-header-cell">Request ID</div>
              </div>
              {experiment.runs.map((run) => (
                <div
                  key={run.run_id}
                  className={`run-row ${selectedRun?.run_id === run.run_id ? 'selected' : ''}`}
                  onClick={() => setSelectedRun(run)}
                >
                  <div className="run-cell run-name">{run.run_name}</div>
                  <div className="run-cell status">
                    {getStatusIcon(run.status)}
                    <span>{run.status}</span>
                  </div>
                  <div className="run-cell model">{run.model_name || 'N/A'}</div>
                  <div className="run-cell timestamp">{formatTimestamp(run.start_time)}</div>
                  <div className="run-cell duration">{formatDuration(run.start_time, run.end_time)}</div>
                  <div className="run-cell request-id">{run.request_id?.substring(0, 8) || 'N/A'}</div>
                </div>
              ))}
            </div>

            {selectedRun && (
              <div className="run-details-panel">
                <div className="details-header">
                  <h3>Run Details</h3>
                  <button className="close-button" onClick={() => setSelectedRun(null)}>×</button>
                </div>
                <div className="details-content">
                  <div className="detail-section">
                    <h4>Run Information</h4>
                    <div className="detail-item">
                      <span className="detail-label">Run ID:</span>
                      <span className="detail-value">{selectedRun.run_id}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Run Name:</span>
                      <span className="detail-value">{selectedRun.run_name}</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Status:</span>
                      <span className={`detail-value ${selectedRun.status.toLowerCase()}`}>
                        {selectedRun.status}
                      </span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Start Time:</span>
                      <span className="detail-value">{formatTimestamp(selectedRun.start_time)}</span>
                    </div>
                    {selectedRun.end_time && (
                      <div className="detail-item">
                        <span className="detail-label">End Time:</span>
                        <span className="detail-value">{formatTimestamp(selectedRun.end_time)}</span>
                      </div>
                    )}
                    {selectedRun.request_id && (
                      <div className="detail-item">
                        <span className="detail-label">Request ID:</span>
                        <span className="detail-value">{selectedRun.request_id}</span>
                      </div>
                    )}
                  </div>

                  {Object.keys(selectedRun.params).length > 0 && (
                    <div className="detail-section">
                      <h4>Parameters</h4>
                      <div className="params-grid">
                        {Object.entries(selectedRun.params).map(([key, value]) => (
                          <div key={key} className="param-item">
                            <span className="param-key">{key}:</span>
                            <span className="param-value">{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {Object.keys(selectedRun.metrics).length > 0 && (
                    <div className="detail-section">
                      <h4>Metrics</h4>
                      <div className="metrics-grid">
                        {Object.entries(selectedRun.metrics).map(([key, value]) => (
                          <div key={key} className="metric-item">
                            <span className="metric-key">{key}:</span>
                            <span className="metric-value">{value.toFixed(4)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : experiment ? (
          <div className="empty-state">
            <p>No runs found in this experiment. Run evaluations to see results here.</p>
          </div>
        ) : null}
      </div>

      {healthStatus && (
        <div className="status-section">
          <h2>System Status</h2>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">LLM Provider:</span>
              <span className="status-value">{healthStatus.llm_provider || 'N/A'}</span>
            </div>
            <div className="status-item">
              <span className="status-label">Embedding Provider:</span>
              <span className="status-value">{healthStatus.embedding_provider || 'N/A'}</span>
            </div>
            <div className="status-item">
              <span className="status-label">MLflow Tracking:</span>
              <span className={`status-value ${healthStatus.features?.mlflow_tracking ? 'enabled' : 'disabled'}`}>
                {healthStatus.features?.mlflow_tracking ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            {experiment && (
              <div className="status-item">
                <span className="status-label">Total Runs:</span>
                <span className="status-value">{experiment.run_count}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MLLoggerPage;
