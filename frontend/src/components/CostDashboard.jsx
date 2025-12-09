import { useState, useEffect } from 'react';
import './CostDashboard.css';

export default function CostDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dateRange, setDateRange] = useState('7'); // days

  useEffect(() => {
    fetchDashboardData();
  }, [dateRange]);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Calculate date range
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - parseInt(dateRange) * 24 * 60 * 60 * 1000)
        .toISOString()
        .split('T')[0];

      const response = await fetch(
        `http://localhost:8001/api/metrics/dashboard?start_date=${startDate}&end_date=${endDate}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch dashboard data');
      }

      const data = await response.json();
      setDashboardData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="cost-dashboard">
        <div className="loading-state">Loading cost analytics...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="cost-dashboard">
        <div className="error-state">
          <h3>Error Loading Dashboard</h3>
          <p>{error}</p>
          <button onClick={fetchDashboardData}>Retry</button>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return null;
  }

  const { daily_costs, model_costs, workspace_costs, expensive_queries, model_performance } = dashboardData;

  // Calculate totals
  const totalCost = daily_costs?.reduce((sum, day) => sum + day.cost, 0) || 0;
  const avgDailyCost = daily_costs?.length > 0 ? totalCost / daily_costs.length : 0;

  return (
    <div className="cost-dashboard">
      <div className="dashboard-header">
        <h1>Cost Analytics Dashboard</h1>
        <div className="date-range-selector">
          <label>Date Range:</label>
          <select value={dateRange} onChange={(e) => setDateRange(e.target.value)}>
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card">
          <h3>Total Cost</h3>
          <div className="metric-value">${totalCost.toFixed(2)}</div>
          <div className="metric-label">{dateRange} days</div>
        </div>

        <div className="summary-card">
          <h3>Average Daily</h3>
          <div className="metric-value">${avgDailyCost.toFixed(2)}</div>
          <div className="metric-label">per day</div>
        </div>

        <div className="summary-card">
          <h3>Total Queries</h3>
          <div className="metric-value">
            {model_performance?.reduce((sum, m) => sum + (m.total_invocations || 0), 0) || 0}
          </div>
          <div className="metric-label">invocations</div>
        </div>

        <div className="summary-card">
          <h3>Success Rate</h3>
          <div className="metric-value">
            {model_performance?.length > 0
              ? (
                  (model_performance.reduce((sum, m) => sum + (m.success_rate || 0), 0) /
                    model_performance.length) *
                  100
                ).toFixed(1)
              : 0}
            %
          </div>
          <div className="metric-label">average</div>
        </div>
      </div>

      {/* Daily Costs Chart */}
      <div className="dashboard-section">
        <h2>Daily Cost Trend</h2>
        <div className="chart-container">
          <div className="bar-chart">
            {daily_costs?.map((day, index) => {
              const maxCost = Math.max(...daily_costs.map((d) => d.cost), 1);
              const barHeight = (day.cost / maxCost) * 100;

              return (
                <div key={index} className="bar-wrapper">
                  <div className="bar" style={{ height: `${barHeight}%` }}>
                    <div className="bar-value">${day.cost.toFixed(2)}</div>
                  </div>
                  <div className="bar-label">{new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Model Costs */}
      <div className="dashboard-section">
        <h2>Cost by Model</h2>
        <div className="model-costs-grid">
          {model_costs?.map((model, index) => (
            <div key={index} className="model-cost-card">
              <div className="model-name">{model.model_name}</div>
              <div className="model-cost">${model.total_cost?.toFixed(2) || '0.00'}</div>
              <div className="model-percentage">
                {((model.percentage || 0) * 100).toFixed(1)}% of total
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Workspace Costs */}
      {workspace_costs && workspace_costs.length > 0 && (
        <div className="dashboard-section">
          <h2>Cost by Workspace</h2>
          <div className="workspace-costs-list">
            {workspace_costs.map((workspace, index) => {
              const totalWorkspaceCost = workspace_costs.reduce((sum, w) => sum + (w.total_cost || 0), 0);
              const percentage = totalWorkspaceCost > 0 ? (workspace.total_cost / totalWorkspaceCost) * 100 : 0;

              return (
                <div key={index} className="workspace-cost-item">
                  <div className="workspace-info">
                    <span className="workspace-name">{workspace.workspace}</span>
                    <span className="workspace-cost">${workspace.total_cost?.toFixed(2) || '0.00'}</span>
                  </div>
                  <div className="workspace-bar">
                    <div className="workspace-bar-fill" style={{ width: `${percentage}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Model Performance */}
      <div className="dashboard-section">
        <h2>Model Performance</h2>
        <div className="performance-table">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Invocations</th>
                <th>Success Rate</th>
                <th>Avg Latency</th>
                <th>Total Cost</th>
              </tr>
            </thead>
            <tbody>
              {model_performance?.map((model, index) => (
                <tr key={index}>
                  <td className="model-name-cell">{model.model_name}</td>
                  <td>{model.total_invocations || 0}</td>
                  <td>
                    <span className={`success-rate ${(model.success_rate || 0) > 0.95 ? 'high' : (model.success_rate || 0) > 0.8 ? 'medium' : 'low'}`}>
                      {((model.success_rate || 0) * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td>{model.avg_latency_ms ? `${model.avg_latency_ms.toFixed(0)}ms` : 'N/A'}</td>
                  <td>${model.total_cost?.toFixed(2) || '0.00'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Expensive Queries */}
      {expensive_queries && expensive_queries.length > 0 && (
        <div className="dashboard-section">
          <h2>Most Expensive Queries</h2>
          <div className="expensive-queries-list">
            {expensive_queries.slice(0, 10).map((query, index) => (
              <div key={index} className="expensive-query-item">
                <div className="query-rank">#{index + 1}</div>
                <div className="query-details">
                  <div className="query-preview">{query.query?.substring(0, 100) || 'N/A'}...</div>
                  <div className="query-meta">
                    {query.timestamp && new Date(query.timestamp).toLocaleString()} • ${query.cost?.toFixed(2) || '0.00'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
