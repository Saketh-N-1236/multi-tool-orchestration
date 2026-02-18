import { useState, useEffect, useMemo } from 'react';
import { ExternalLink, RefreshCw, Database, Activity, TrendingUp, Clock, CheckCircle, XCircle, AlertCircle, TrendingDown } from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { healthAPI, mlflowAPI } from '../services/api';
import './MLLoggerPage.css';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

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
    // MLflow returns timestamps in milliseconds, not seconds
    return new Date(timestamp).toLocaleString();
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
    // Both startTime and endTime are in milliseconds
    const duration = (endTime - startTime) / 1000; // Convert to seconds
    if (duration < 1) return `${(duration * 1000).toFixed(0)}ms`;
    if (duration < 60) return `${duration.toFixed(1)}s`;
    return `${(duration / 60).toFixed(1)}m`;
  };

  // Process AI Judge metrics from all runs
  const aiJudgeData = useMemo(() => {
    if (!experiment || !experiment.runs || experiment.runs.length === 0) {
      return null;
    }

    // Filter runs that have AI judge metrics
    const runsWithAIJudge = experiment.runs.filter(run => 
      Object.keys(run.metrics).some(key => key.startsWith('ai_judge_'))
    );

    if (runsWithAIJudge.length === 0) {
      return null;
    }

    // Sort by start_time (oldest first for trend analysis)
    const sortedRuns = [...runsWithAIJudge].sort((a, b) => a.start_time - b.start_time);

    // Extract data points for each metric
    const metrics = ['correctness', 'relevance', 'completeness', 'tool_usage', 'overall_score'];
    const chartData: Record<string, { labels: string[], values: number[] }> = {};
    
    metrics.forEach(metric => {
      const key = `ai_judge_${metric}`;
      chartData[metric] = {
        labels: sortedRuns.map(run => 
          new Date(run.start_time).toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
          })
        ),
        values: sortedRuns.map(run => run.metrics[key] || 0)
      };
    });

    // Calculate statistics
    const stats: Record<string, {
      average: number;
      min: number;
      max: number;
      latest: number;
      trend: 'up' | 'down' | 'stable';
      change: number;
    }> = {};

    metrics.forEach(metric => {
      const values = chartData[metric].values;
      if (values.length === 0) return;

      const average = values.reduce((sum, val) => sum + val, 0) / values.length;
      const min = Math.min(...values);
      const max = Math.max(...values);
      const latest = values[values.length - 1];
      
      // Calculate trend (compare last 3 vs previous 3, or last vs first if less than 6)
      let trend: 'up' | 'down' | 'stable' = 'stable';
      let change = 0;
      
      if (values.length >= 6) {
        const recent = values.slice(-3).reduce((sum, val) => sum + val, 0) / 3;
        const previous = values.slice(-6, -3).reduce((sum, val) => sum + val, 0) / 3;
        change = ((recent - previous) / previous) * 100;
        trend = change > 2 ? 'up' : change < -2 ? 'down' : 'stable';
      } else if (values.length >= 2) {
        const first = values[0];
        const last = values[values.length - 1];
        change = ((last - first) / first) * 100;
        trend = change > 2 ? 'up' : change < -2 ? 'down' : 'stable';
      }

      stats[metric] = {
        average: average,
        min: min,
        max: max,
        latest: latest,
        trend: trend,
        change: change
      };
    });

    return {
      chartData,
      stats,
      totalRuns: sortedRuns.length,
      dateRange: {
        start: sortedRuns[0].start_time,
        end: sortedRuns[sortedRuns.length - 1].start_time
      }
    };
  }, [experiment]);

  // Chart options
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: false,
      },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: 1.0,
        ticks: {
          stepSize: 0.1,
          callback: function(value: any) {
            return value.toFixed(1);
          }
        }
      },
      x: {
        ticks: {
          maxRotation: 45,
          minRotation: 45,
        }
      }
    },
    elements: {
      line: {
        tension: 0.4,
        fill: true,
      },
      point: {
        radius: 4,
        hoverRadius: 6,
      }
    }
  };

  // Get chart data for a specific metric
  const getChartData = (metric: string) => {
    if (!aiJudgeData) return null;
    
    const data = aiJudgeData.chartData[metric];
    if (!data) return null;

    return {
      labels: data.labels,
      datasets: [
        {
          label: metric.charAt(0).toUpperCase() + metric.slice(1).replace(/_/g, ' '),
          data: data.values,
          borderColor: getMetricColor(metric),
          backgroundColor: getMetricColor(metric, 0.1),
          borderWidth: 2,
          fill: true,
        }
      ]
    };
  };

  const getMetricColor = (metric: string, opacity: number = 1) => {
    const colors: Record<string, string> = {
      correctness: `rgba(34, 197, 94, ${opacity})`,      // Green
      relevance: `rgba(59, 130, 246, ${opacity})`,        // Blue
      completeness: `rgba(168, 85, 247, ${opacity})`,     // Purple
      tool_usage: `rgba(251, 146, 60, ${opacity})`,       // Orange
      overall_score: `rgba(239, 68, 68, ${opacity})`,     // Red
    };
    return colors[metric] || `rgba(100, 100, 100, ${opacity})`;
  };

  const getTrendIcon = (trend: 'up' | 'down' | 'stable') => {
    switch (trend) {
      case 'up':
        return <TrendingUp size={16} className="trend-up" />;
      case 'down':
        return <TrendingDown size={16} className="trend-down" />;
      default:
        return <Activity size={16} className="trend-stable" />;
    }
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

      {/* AI Judge Performance Dashboard */}
      {aiJudgeData && (
        <div className="ai-judge-dashboard">
          <div className="section-header">
            <h2>AI Judge Performance Dashboard</h2>
            <div className="dashboard-stats">
              <span className="stat-badge">
                <Activity size={16} />
                {aiJudgeData.totalRuns} Runs Analyzed
              </span>
              <span className="stat-badge">
                <Clock size={16} />
                {new Date(aiJudgeData.dateRange.start).toLocaleDateString()} - {new Date(aiJudgeData.dateRange.end).toLocaleDateString()}
              </span>
            </div>
          </div>

          {/* Summary Cards */}
          <div className="summary-cards">
            {Object.entries(aiJudgeData.stats).map(([metric, stat]) => (
              <div key={metric} className="summary-card">
                <div className="card-header">
                  <h3>{metric.charAt(0).toUpperCase() + metric.slice(1).replace(/_/g, ' ')}</h3>
                  {getTrendIcon(stat.trend)}
                </div>
                <div className="card-content">
                  <div className="metric-value">
                    <span className="latest-value">{stat.latest.toFixed(3)}</span>
                    <span className={`change-value ${stat.trend}`}>
                      {stat.change > 0 ? '+' : ''}{stat.change.toFixed(1)}%
                    </span>
                  </div>
                  <div className="metric-stats">
                    <div className="stat-item">
                      <span className="stat-label">Avg:</span>
                      <span className="stat-value">{stat.average.toFixed(3)}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">Min:</span>
                      <span className="stat-value">{stat.min.toFixed(3)}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-label">Max:</span>
                      <span className="stat-value">{stat.max.toFixed(3)}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Trend Charts */}
          <div className="charts-container">
            <div className="chart-section">
              <h3>Overall Score Trend</h3>
              <div className="chart-wrapper">
                {getChartData('overall_score') && (
                  <Line data={getChartData('overall_score')!} options={chartOptions} />
                )}
              </div>
            </div>

            <div className="charts-grid">
              <div className="chart-section">
                <h3>Correctness</h3>
                <div className="chart-wrapper">
                  {getChartData('correctness') && (
                    <Line data={getChartData('correctness')!} options={chartOptions} />
                  )}
                </div>
              </div>

              <div className="chart-section">
                <h3>Relevance</h3>
                <div className="chart-wrapper">
                  {getChartData('relevance') && (
                    <Line data={getChartData('relevance')!} options={chartOptions} />
                  )}
                </div>
              </div>

              <div className="chart-section">
                <h3>Completeness</h3>
                <div className="chart-wrapper">
                  {getChartData('completeness') && (
                    <Line data={getChartData('completeness')!} options={chartOptions} />
                  )}
                </div>
              </div>

              <div className="chart-section">
                <h3>Tool Usage</h3>
                <div className="chart-wrapper">
                  {getChartData('tool_usage') && (
                    <Line data={getChartData('tool_usage')!} options={chartOptions} />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

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
                      
                      {/* AI Judge Metrics Section */}
                      {Object.keys(selectedRun.metrics).some(key => key.startsWith('ai_judge_')) && (
                        <div className="ai-judge-metrics">
                          <h5>AI Judge Evaluation</h5>
                          <div className="metrics-grid">
                            {Object.entries(selectedRun.metrics)
                              .filter(([key]) => key.startsWith('ai_judge_'))
                              .map(([key, value]) => {
                                // Format metric name for display
                                const displayName = key
                                  .replace('ai_judge_', '')
                                  .replace(/_/g, ' ')
                                  .replace(/\b\w/g, l => l.toUpperCase());
                                return (
                                  <div key={key} className="metric-item ai-judge-metric">
                                    <span className="metric-key">{displayName}:</span>
                                    <span className="metric-value">{value.toFixed(4)}</span>
                                  </div>
                                );
                              })}
                          </div>
                        </div>
                      )}
                      
                      {/* Other Metrics Section */}
                      {Object.keys(selectedRun.metrics).some(key => !key.startsWith('ai_judge_')) && (
                        <div className="other-metrics">
                          <h5>Other Metrics</h5>
                          <div className="metrics-grid">
                            {Object.entries(selectedRun.metrics)
                              .filter(([key]) => !key.startsWith('ai_judge_'))
                              .map(([key, value]) => (
                                <div key={key} className="metric-item">
                                  <span className="metric-key">{key}:</span>
                                  <span className="metric-value">{value.toFixed(4)}</span>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}
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
