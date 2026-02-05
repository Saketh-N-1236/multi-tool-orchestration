import { useState, useEffect } from 'react';
import { analyticsAPI } from '../services/api';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Line as LineChart, Bar as BarChart, Doughnut as DoughnutChart } from 'react-chartjs-2';
import './AnalyticsPage.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const AnalyticsPage = () => {
  const [overview, setOverview] = useState<any>(null);
  const [tools, setTools] = useState<any>(null);
  const [timeSeries, setTimeSeries] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeWindow, setTimeWindow] = useState(24);

  useEffect(() => {
    loadData();
  }, [timeWindow]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [overviewData, toolsData, timeSeriesData] = await Promise.all([
        analyticsAPI.getOverview(),
        analyticsAPI.getTools(),
        analyticsAPI.getTimeSeries(timeWindow, 60),
      ]);
      setOverview(overviewData);
      setTools(toolsData);
      setTimeSeries(timeSeriesData);
    } catch (error: any) {
      console.error('Failed to load analytics:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to load analytics data');
      // Set empty states on error
      setOverview(null);
      setTools(null);
      setTimeSeries(null);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="analytics-page">
        <div className="loading-state">Loading analytics...</div>
      </div>
    );
  }

  if (error && !overview) {
    return (
      <div className="analytics-page">
        <div className="error-state">
          <h3>Error Loading Analytics</h3>
          <p>{error}</p>
          <button className="retry-button" onClick={() => { setError(null); loadData(); }}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Transform backend response to match frontend expectations
  const statusDistribution = overview?.requests_by_status || {};
  const statusChartData = Object.keys(statusDistribution).length > 0 ? {
    labels: Object.keys(statusDistribution),
    datasets: [
      {
        label: 'Requests',
        data: Object.values(statusDistribution),
        backgroundColor: [
          'rgba(102, 126, 234, 0.8)',
          'rgba(34, 197, 94, 0.8)',
          'rgba(239, 68, 68, 0.8)',
          'rgba(255, 193, 7, 0.8)',
        ],
      },
    ],
  } : null;

  // Transform tools from dict to array
  const toolsArray = tools?.tools ? Object.entries(tools.tools).map(([name, data]: [string, any]) => ({
    tool_name: name,
    call_count: data.call_count || 0,
    success_count: data.success_count || 0,
    failure_count: data.failure_count || 0,
    average_duration: data.avg_duration || 0,
  })) : [];

  const toolsChartData = toolsArray.length > 0 ? {
    labels: toolsArray.slice(0, 10).map((t: any) => t.tool_name),
    datasets: [
      {
        label: 'Call Count',
        data: toolsArray.slice(0, 10).map((t: any) => t.call_count),
        backgroundColor: 'rgba(102, 126, 234, 0.8)',
      },
    ],
  } : null;

  // Extract time series data from response
  const timeSeriesData = timeSeries?.time_series || [];
  const timeSeriesChartData = timeSeriesData.length > 0 ? {
    labels: timeSeriesData.map((d: any) => new Date(d.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'Requests',
        data: timeSeriesData.map((d: any) => d.request_count || 0),
        borderColor: 'rgb(102, 126, 234)',
        backgroundColor: 'rgba(102, 126, 234, 0.1)',
        fill: true,
        tension: 0.4,
      },
    ],
  } : null;

  return (
    <div className="analytics-page">
      <div className="analytics-header">
        <h1>Analytics & Monitoring</h1>
        <div className="header-controls">
          <select
            value={timeWindow}
            onChange={(e) => setTimeWindow(Number(e.target.value))}
            className="time-window-select"
          >
            <option value={1}>Last Hour</option>
            <option value={24}>Last 24 Hours</option>
            <option value={168}>Last Week</option>
            <option value={720}>Last Month</option>
          </select>
        </div>
      </div>

      {overview && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Total Requests</div>
            <div className="stat-value">{overview.total_requests || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Successful</div>
            <div className="stat-value success">{overview.successful_requests || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value error">{overview.failed_requests || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Response Time</div>
            <div className="stat-value">
              {overview.avg_duration
                ? `${(overview.avg_duration * 1000).toFixed(0)}ms`
                : 'N/A'}
            </div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Total Tool Calls</div>
            <div className="stat-value">{overview.total_tool_calls || 0}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Unique Tools</div>
            <div className="stat-value">{tools?.total_unique_tools || 0}</div>
          </div>
        </div>
      )}

      <div className="charts-grid">
        {statusChartData && (
          <div className="chart-card">
            <h3>Status Distribution</h3>
            <DoughnutChart data={statusChartData} />
          </div>
        )}

        {toolsChartData && (
          <div className="chart-card">
            <h3>Top Tools Usage</h3>
            <BarChart
              data={toolsChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    display: false,
                  },
                },
              }}
            />
          </div>
        )}

        {timeSeriesChartData && (
          <div className="chart-card full-width">
            <h3>Request Timeline</h3>
            <LineChart
              data={timeSeriesChartData}
              options={{
                responsive: true,
                plugins: {
                  legend: {
                    display: true,
                  },
                },
                scales: {
                  y: {
                    beginAtZero: true,
                  },
                },
              }}
            />
          </div>
        )}
      </div>

      {toolsArray.length > 0 && (
        <div className="tools-table-card">
          <h3>Tool Usage Statistics</h3>
          <table className="tools-table">
            <thead>
              <tr>
                <th>Tool Name</th>
                <th>Call Count</th>
                <th>Success</th>
                <th>Failure</th>
                <th>Avg Duration</th>
              </tr>
            </thead>
            <tbody>
              {toolsArray.map((tool: any, idx: number) => (
                <tr key={idx}>
                  <td>{tool.tool_name}</td>
                  <td>{tool.call_count}</td>
                  <td className="success">{tool.success_count}</td>
                  <td className="error">{tool.failure_count}</td>
                  <td>
                    {tool.average_duration
                      ? `${(tool.average_duration * 1000).toFixed(0)}ms`
                      : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default AnalyticsPage;
