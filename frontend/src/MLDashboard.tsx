import React, { useEffect, useState } from 'react';
import './MLDashboard.css';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ScatterChart, Scatter, ReferenceLine
} from 'recharts';

interface Metrics {
  accuracy: number;
  log_loss: number;
  roc_auc: number;
  n_samples: number;
  n_folds: number;
  selected_model?: string;
  selected_model_metrics?: any;
  best_feature_set?: string;
  best_variant?: string;
}

interface CalibrationPoint {
  bin: number;
  bin_low: number;
  bin_high: number;
  count: number;
  mean_pred: number;
  mean_true: number;
  diff: number;
}

interface AblationResult {
  feature_set: string;
  n_features: number;
  variant: string;
  accuracy: number;
  log_loss: number;
  roc_auc: number;
}

interface DecileData {
  decile: number;
  bin_low: number;
  bin_high: number;
  count: number;
  mean_pred: number;
  mean_true: number;
  calibration_diff: number;
}

interface PicksSummary {
  decile_analysis?: DecileData[];
  threshold_policy?: any[];
  topk_policy?: any[];
  hypothetical_ev?: any;
}

interface Coefficient {
  feature: string;
  coefficient: number;
}

const API_BASE = 'http://localhost:8000/api';

export default function MLDashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [calibration, setCalibration] = useState<CalibrationPoint[]>([]);
  const [ablation, setAblation] = useState<AblationResult[]>([]);
  const [deciles, setDeciles] = useState<DecileData[]>([]);
  const [picksSummary, setPicksSummary] = useState<PicksSummary | null>(null);
  const [coefficients, setCoefficients] = useState<Coefficient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAllData();
  }, []);

  const loadAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, calRes, ablRes, decRes, picksRes, coefRes] = await Promise.all([
        fetch(`${API_BASE}/metrics`).catch(() => null),
        fetch(`${API_BASE}/calibration`).catch(() => null),
        fetch(`${API_BASE}/ablation`).catch(() => null),
        fetch(`${API_BASE}/deciles`).catch(() => null),
        fetch(`${API_BASE}/picks_summary`).catch(() => null),
        fetch(`${API_BASE}/coefficients`).catch(() => null),
      ]);

      if (metricsRes?.ok) setMetrics(await metricsRes.json());
      if (calRes?.ok) setCalibration(await calRes.json());
      if (ablRes?.ok) setAblation(await ablRes.json());
      if (decRes?.ok) setDeciles(await decRes.json());
      if (picksRes?.ok) setPicksSummary(await picksRes.json());
      if (coefRes?.ok) {
        const coefData = await coefRes.json();
        // Handle both {coefficients: [...]} and [{...}] formats
        if (Array.isArray(coefData)) {
          setCoefficients(coefData);
        } else if (coefData.coefficients) {
          setCoefficients(coefData.coefficients);
        } else {
          setCoefficients([]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-container"><div className="loading">Loading ML Dashboard...</div></div>;
  }

  if (error) {
    return <div className="dashboard-container"><div className="error">Error: {error}</div></div>;
  }

  // Prepare calibration chart data
  const calibrationChartData = calibration.map(d => ({
    bin: d.bin,
    predicted: d.mean_pred,
    actual: d.mean_true,
    diff: d.diff,
  }));

  // Prepare deciles chart data
  const decilesChartData = deciles.map(d => ({
    decile: d.decile,
    predicted: d.mean_pred,
    actual: d.mean_true,
    count: d.count,
  }));

  // Prepare ablation chart data
  const ablationChartData = ablation.map(a => ({
    name: `${a.feature_set} (${a.variant})`,
    log_loss: a.log_loss,
    accuracy: a.accuracy,
    roc_auc: a.roc_auc,
    feature_set: a.feature_set,
    variant: a.variant,
  }));

  // Sort coefficients by absolute value
  const sortedCoefficients = [...coefficients].sort((a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient));
  const topPositive = sortedCoefficients.filter(c => c.coefficient > 0).slice(0, 10);
  const topNegative = sortedCoefficients.filter(c => c.coefficient < 0).slice(0, 10);

  return (
    <div className="dashboard-container">
      <h1>ML Pipeline Dashboard</h1>

      {/* Overview Cards */}
      <section className="section">
        <h2>Overview</h2>
        <div className="cards-grid">
          <div className="card">
            <div className="card-label">Accuracy</div>
            <div className="card-value">{metrics?.accuracy ? (metrics.accuracy * 100).toFixed(1) + '%' : 'N/A'}</div>
          </div>
          <div className="card">
            <div className="card-label">Log Loss</div>
            <div className="card-value">{metrics?.log_loss?.toFixed(3) || 'N/A'}</div>
            <div className="card-note">Primary metric (lower is better)</div>
          </div>
          <div className="card">
            <div className="card-label">ROC-AUC</div>
            <div className="card-value">{metrics?.roc_auc?.toFixed(3) || 'N/A'}</div>
          </div>
          <div className="card">
            <div className="card-label">Samples</div>
            <div className="card-value">{metrics?.n_samples || 'N/A'}</div>
          </div>
          <div className="card">
            <div className="card-label">Folds</div>
            <div className="card-value">{metrics?.n_folds || 'N/A'}</div>
          </div>
          <div className="card">
            <div className="card-label">Best Model</div>
            <div className="card-value">{metrics?.best_feature_set || 'N/A'}</div>
            <div className="card-note">{metrics?.best_variant || ''}</div>
          </div>
        </div>
      </section>

      {/* Calibration Chart */}
      <section className="section">
        <h2>Calibration</h2>
        <p>Predicted probability (mean_pred) vs Actual hit rate (mean_true). Well-calibrated models fall on the diagonal line (y=x).</p>
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart data={calibrationChartData} margin={{ top: 10, right: 30, bottom: 40, left: 40 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              type="number" 
              dataKey="predicted" 
              domain={[0, 1]} 
              label={{ value: 'Mean Predicted', position: 'insideBottom', offset: -5 }} 
            />
            <YAxis 
              type="number" 
              dataKey="actual" 
              domain={[0, 1]} 
              label={{ value: 'Mean Actual', angle: -90, position: 'insideLeft' }} 
            />
            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
            <Legend />
            <Scatter name="Calibration" data={calibrationChartData} fill="#8884d8" />
            {/* Perfect calibration line (y=x) - draw diagonal from (0,0) to (1,1) */}
            <ReferenceLine y={0} x={0} stroke="#82ca9d" strokeDasharray="5 5" label={{ value: 'Perfect (y=x)', position: 'topRight' }} />
            <ReferenceLine y={1} x={1} stroke="#82ca9d" strokeDasharray="5 5" strokeOpacity={0.5} />
          </ScatterChart>
        </ResponsiveContainer>
        <p className="note">Points on the diagonal (y=x) indicate perfect calibration. Points above the line indicate underconfidence, points below indicate overconfidence.</p>
      </section>

      {/* Deciles Chart */}
      <section className="section">
        <h2>Performance by Confidence Decile</h2>
        <p>Model performance across confidence levels (1 = low, 10 = high)</p>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={decilesChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="decile" label={{ value: 'Decile', position: 'insideBottom', offset: -5 }} />
            <YAxis label={{ value: 'Hit Rate', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="predicted" stroke="#8884d8" name="Predicted" />
            <Line type="monotone" dataKey="actual" stroke="#82ca9d" name="Actual" />
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Ablation Comparison */}
      <section className="section">
        <h2>Ablation Study</h2>
        <p>Feature set comparison (lower Log Loss = better)</p>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={ablationChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="log_loss" fill="#8884d8" name="Log Loss" />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Threshold Policy Table */}
      <section className="section">
        <h2>Threshold Policy Results</h2>
        {picksSummary?.threshold_policy && picksSummary.threshold_policy.length > 0 ? (
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
              {picksSummary.threshold_policy.map((p: any, i: number) => (
                <tr key={i}>
                  <td>{p.threshold}</td>
                  <td>{p.total_picks}</td>
                  <td>{p.overall_hit_rate ? (p.overall_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>
                    {p.overall_hit_rate_ci_lower !== undefined && p.overall_hit_rate_ci_upper !== undefined
                      ? `[${(p.overall_hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.overall_hit_rate_ci_upper * 100).toFixed(1)}%]`
                      : 'N/A'}
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

      {/* Top-K Policy Table */}
      <section className="section">
        <h2>Top-K Policy Results</h2>
        {picksSummary?.topk_policy && picksSummary.topk_policy.length > 0 ? (
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
              {picksSummary.topk_policy.map((p: any, i: number) => (
                <tr key={i}>
                  <td>{p.k}</td>
                  <td>{p.total_picks}</td>
                  <td>{p.overall_hit_rate ? (p.overall_hit_rate * 100).toFixed(1) + '%' : 'N/A'}</td>
                  <td>
                    {p.overall_hit_rate_ci_lower !== undefined && p.overall_hit_rate_ci_upper !== undefined
                      ? `[${(p.overall_hit_rate_ci_lower * 100).toFixed(1)}%, ${(p.overall_hit_rate_ci_upper * 100).toFixed(1)}%]`
                      : 'N/A'}
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

      {/* Coefficients Table */}
      <section className="section">
        <h2>Model Coefficients</h2>
        <div className="coefficients-grid">
          <div>
            <h3>Top Positive</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Coefficient</th>
                </tr>
              </thead>
              <tbody>
                {topPositive.map((c, i) => (
                  <tr key={i}>
                    <td>{c.feature}</td>
                    <td className={c.coefficient > 0 ? 'positive' : 'negative'}>
                      {c.coefficient.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h3>Top Negative</h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Coefficient</th>
                </tr>
              </thead>
              <tbody>
                {topNegative.map((c, i) => (
                  <tr key={i}>
                    <td>{c.feature}</td>
                    <td className={c.coefficient > 0 ? 'positive' : 'negative'}>
                      {c.coefficient.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {coefficients.length > 0 && (
          <p className="note">
            Intercept: {coefficients.find(c => c.feature === 'intercept' || c.feature === '_intercept')?.coefficient?.toFixed(4) || 'N/A'}
          </p>
        )}
      </section>

      <div className="warning-box">
        <strong>⚠️ Important:</strong> All results are from backtesting on historical data only. This is not a profitability claim. 
        Hypothetical EV calculations assume -110 odds and perfect execution.
      </div>
    </div>
  );
}
