import React, { useEffect, useState } from 'react';
import './MLDashboard.css';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

const API_BASE = 'http://localhost:8000/api';

interface Metrics {
  accuracy: number;
  log_loss: number;
  roc_auc: number;
  n_samples: number;
  n_folds: number;
}

interface Timeframe {
  min_date: string;
  max_date: string;
  n_samples: number;
}

interface PicksSummary {
  threshold_policy?: any[];
  topk_policy?: any[];
}

interface DecileData {
  decile: number;
  mean_pred: number;
  mean_true: number;
  count: number;
}

interface Pick {
  date?: string;
  game_id?: string;
  team_id?: string;
  TEAM_TOTAL_LINE?: number;
  y_true?: number;
  p_hat?: number;
  predicted_side?: string;
  confidence?: number;
  fold?: number;
}

export default function BacktestReview() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe | null>(null);
  const [picksSummary, setPicksSummary] = useState<PicksSummary | null>(null);
  const [deciles, setDeciles] = useState<DecileData[]>([]);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [selectedThreshold, setSelectedThreshold] = useState<number | null>(null);
  const [selectedTopK, setSelectedTopK] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, timeframeRes, picksSummaryRes, decilesRes, picksRes] = await Promise.all([
        fetch(`${API_BASE}/metrics`).catch(() => null),
        fetch(`${API_BASE}/timeframe`).catch(() => null),
        fetch(`${API_BASE}/picks_summary`).catch(() => null),
        fetch(`${API_BASE}/deciles`).catch(() => null),
        fetch(`${API_BASE}/picks?limit=50&sort=confidence`).catch(() => null),
      ]);

      if (metricsRes?.ok) setMetrics(await metricsRes.json());
      if (timeframeRes?.ok) setTimeframe(await timeframeRes.json());
      if (picksSummaryRes?.ok) setPicksSummary(await picksSummaryRes.json());
      if (decilesRes?.ok) setDeciles(await decilesRes.json());
      if (picksRes?.ok) {
        const data = await picksRes.json();
        setPicks(data.picks || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-container"><div className="loading">Loading Backtest Review...</div></div>;
  }

  if (error) {
    return <div className="dashboard-container"><div className="error">Error: {error}</div></div>;
  }

  const decilesChartData = deciles.map(d => ({
    decile: d.decile,
    predicted: d.mean_pred,
    actual: d.mean_true,
    count: d.count,
  }));

  const thresholdOptions = picksSummary?.threshold_policy || [];
  const topKOptions = picksSummary?.topk_policy || [];

  return (
    <div className="dashboard-container">
      <h1>Backtest Review</h1>
      <p style={{ marginBottom: 24, color: '#666' }}>
        Evaluate betting performance from historical backtests. All results are hypothetical and assume -110 odds.
      </p>

      {/* Summary Cards */}
      <section className="section">
        <h2>Summary</h2>
        <div className="cards-grid">
          <div className="card">
            <div className="card-label">Total Picks Analyzed</div>
            <div className="card-value">{metrics?.n_samples || 0}</div>
          </div>
          <div className="card">
            <div className="card-label">Overall Hit Rate</div>
            <div className="card-value">{metrics?.accuracy ? (metrics.accuracy * 100).toFixed(1) + '%' : 'N/A'}</div>
          </div>
          <div className="card">
            <div className="card-label">Timeframe</div>
            <div className="card-value">
              {timeframe?.min_date && timeframe?.max_date 
                ? `${timeframe.min_date} to ${timeframe.max_date}`
                : 'N/A'}
            </div>
          </div>
          <div className="card">
            <div className="card-label">Folds</div>
            <div className="card-value">{metrics?.n_folds || 'N/A'}</div>
          </div>
        </div>
      </section>

      {/* Threshold Explorer */}
      <section className="section">
        <h2>Threshold Policy Explorer</h2>
        <p>Pick Over if p≥threshold, Under if p≤(1-threshold). Higher thresholds = fewer, more confident picks.</p>
        {thresholdOptions.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Threshold</th>
                <th>Total Picks</th>
                <th>Hit Rate</th>
                <th>Hit Rate CI</th>
                <th>Over Picks</th>
                <th>Over Hit Rate</th>
                <th>Under Picks</th>
                <th>Under Hit Rate</th>
              </tr>
            </thead>
            <tbody>
              {thresholdOptions.map((p: any, i: number) => (
                <tr 
                  key={i}
                  onClick={() => setSelectedThreshold(p.threshold)}
                  style={{ cursor: 'pointer', backgroundColor: selectedThreshold === p.threshold ? '#f0f0f0' : 'white' }}
                >
                  <td>{p.threshold}</td>
                  <td>{p.total_picks || p.num_picks || 0}</td>
                  <td>{p.overall_hit_rate || p.hit_rate ? ((p.overall_hit_rate || p.hit_rate) * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>
                    {p.overall_hit_rate_ci_lower !== undefined && p.overall_hit_rate_ci_upper !== undefined
                      ? `[${(p.overall_hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.overall_hit_rate_ci_upper * 100).toFixed(1)}%]`
                      : (p.hit_rate_ci_lower !== undefined && p.hit_rate_ci_upper !== undefined
                        ? `[${(p.hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.hit_rate_ci_upper * 100).toFixed(1)}%]`
                        : 'N/A')}
                  </td>
                  <td>{p.over_pick_count || 0}</td>
                  <td>{p.over_hit_rate ? (p.over_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>{p.under_pick_count || 0}</td>
                  <td>{p.under_hit_rate ? (p.under_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No threshold policy data available</p>
        )}
      </section>

      {/* Top-K Explorer */}
      <section className="section">
        <h2>Top-K Policy Explorer</h2>
        <p>Pick top K most confident predictions per fold. Selective strategy focusing on highest confidence.</p>
        {topKOptions.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>K</th>
                <th>Total Picks</th>
                <th>Hit Rate</th>
                <th>Hit Rate CI</th>
                <th>Over Picks</th>
                <th>Over Hit Rate</th>
                <th>Under Picks</th>
                <th>Under Hit Rate</th>
              </tr>
            </thead>
            <tbody>
              {topKOptions.map((p: any, i: number) => (
                <tr 
                  key={i}
                  onClick={() => setSelectedTopK(p.k)}
                  style={{ cursor: 'pointer', backgroundColor: selectedTopK === p.k ? '#f0f0f0' : 'white' }}
                >
                  <td>{p.k}</td>
                  <td>{p.total_picks || p.num_picks || 0}</td>
                  <td>{p.overall_hit_rate || p.hit_rate ? ((p.overall_hit_rate || p.hit_rate) * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>
                    {p.overall_hit_rate_ci_lower !== undefined && p.overall_hit_rate_ci_upper !== undefined
                      ? `[${(p.overall_hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.overall_hit_rate_ci_upper * 100).toFixed(1)}%]`
                      : (p.hit_rate_ci_lower !== undefined && p.hit_rate_ci_upper !== undefined
                        ? `[${(p.hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.hit_rate_ci_upper * 100).toFixed(1)}%]`
                        : 'N/A')}
                  </td>
                  <td>{p.over_pick_count || 0}</td>
                  <td>{p.over_hit_rate ? (p.over_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>{p.under_pick_count || 0}</td>
                  <td>{p.under_hit_rate ? (p.under_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No top-K policy data available</p>
        )}
      </section>

      {/* Decile Performance Chart */}
      <section className="section">
        <h2>Performance by Confidence Decile</h2>
        <p>Model performance across confidence levels (1 = low confidence, 10 = high confidence)</p>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={decilesChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="decile" label={{ value: 'Decile (Confidence Level)', position: 'insideBottom', offset: -5 }} />
            <YAxis label={{ value: 'Hit Rate', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="predicted" stroke="#8884d8" name="Predicted" />
            <Line type="monotone" dataKey="actual" stroke="#82ca9d" name="Actual" />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Example Picks Table */}
      <section className="section">
        <h2>Example Picks (Top 50 by Confidence)</h2>
        <p>Top predictions from backtest, sorted by confidence |p-0.5|</p>
        {picks.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Game ID</th>
                <th>Team ID</th>
                <th>Line</th>
                <th>Pred Prob</th>
                <th>Side</th>
                <th>Confidence</th>
                <th>Actual (Hit)</th>
              </tr>
            </thead>
            <tbody>
              {picks.map((pick, i) => (
                <tr key={i}>
                  <td>{pick.date || 'N/A'}</td>
                  <td>{pick.game_id || 'N/A'}</td>
                  <td>{pick.team_id || 'N/A'}</td>
                  <td>{pick.TEAM_TOTAL_LINE?.toFixed(1) || 'N/A'}</td>
                  <td>{pick.p_hat ? (pick.p_hat * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td style={{ fontWeight: pick.p_hat && pick.p_hat >= 0.5 ? 600 : 400 }}>
                    {pick.predicted_side || 'N/A'}
                  </td>
                  <td>{pick.confidence ? (pick.confidence * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td style={{ color: pick.y_true === 1 ? '#2e7d32' : '#c62828', fontWeight: 600 }}>
                    {pick.y_true !== undefined ? (pick.y_true === 1 ? '✓ Hit' : '✗ Miss') : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No picks data available</p>
        )}
      </section>

      <div className="warning-box">
        <strong>⚠️ Important:</strong> All results are from backtesting on historical data only. This is not a profitability claim.
        Hypothetical EV calculations assume -110 odds and perfect execution.
      </div>
    </div>
  );
}
