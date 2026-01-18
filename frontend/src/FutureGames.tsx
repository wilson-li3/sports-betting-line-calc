import React, { useEffect, useState } from 'react';
import './MLDashboard.css';

const API_BASE = 'http://localhost:8000/api';

interface FutureGame {
  game_id: string;
  team_id?: string;
  date?: string;
  TEAM_ABBREVIATION?: string;
  TEAM_TOTAL_LINE?: number;
  GAME_TOTAL_LINE?: number;
  p_hat: number;
  confidence: number;
  recommended_side: string;
  hypothetical_ev?: number;
}

export default function FutureGames() {
  const [games, setGames] = useState<FutureGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [minConfidence, setMinConfidence] = useState(0.0);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    loadFutureGames();
  }, [minConfidence, dateFrom, dateTo, limit]);

  const loadFutureGames = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: limit.toString(),
        min_confidence: minConfidence.toString(),
      });
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const res = await fetch(`${API_BASE}/future_games?${params}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errorData.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setGames(data.games || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load future games');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="dashboard-container"><div className="loading">Loading Future Games...</div></div>;
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="error">
          Error: {error}
          <br />
          <small>Make sure you have future games data loaded. See README for instructions.</small>
        </div>
      </div>
    );
  }

  // Probability distribution for chart
  const probBins = Array.from({ length: 10 }, (_, i) => ({
    bin: `${i * 10}-${(i + 1) * 10}%`,
    count: games.filter(g => g.p_hat >= i * 0.1 && g.p_hat < (i + 1) * 0.1).length,
  }));

  return (
    <div className="dashboard-container">
      <h1>Future Games Predictions</h1>
      <p style={{ marginBottom: 24, color: '#666' }}>
        Model predictions for upcoming games. Predictions use saved model.joblib and historical data for rolling features.
      </p>

      {/* Filters */}
      <section className="section">
        <h2>Filters</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>
              Min Confidence: {(minConfidence * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="0.5"
              step="0.01"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              style={{ width: '100%', padding: '6px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              style={{ width: '100%', padding: '6px' }}
            />
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, fontWeight: 500 }}>Limit</label>
            <input
              type="number"
              min="1"
              max="1000"
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value) || 100)}
              style={{ width: '100%', padding: '6px' }}
            />
          </div>
        </div>
      </section>

      {/* Summary */}
      <section className="section">
        <h2>Summary</h2>
        <div className="cards-grid">
          <div className="card">
            <div className="card-label">Total Games</div>
            <div className="card-value">{games.length}</div>
          </div>
          <div className="card">
            <div className="card-label">Over Recommendations</div>
            <div className="card-value">
              {games.filter(g => g.recommended_side === 'OVER').length}
            </div>
          </div>
          <div className="card">
            <div className="card-label">Under Recommendations</div>
            <div className="card-value">
              {games.filter(g => g.recommended_side === 'UNDER').length}
            </div>
          </div>
          <div className="card">
            <div className="card-label">Avg Confidence</div>
            <div className="card-value">
              {games.length > 0
                ? (games.reduce((sum, g) => sum + g.confidence, 0) / games.length * 100).toFixed(1) + '%'
                : 'N/A'}
            </div>
          </div>
        </div>
      </section>

      {/* Probability Distribution */}
      {games.length > 0 && (
        <section className="section">
          <h2>Probability Distribution</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {probBins.map((bin, i) => (
              <div key={i} style={{ flex: '1 1 80px', minWidth: 80 }}>
                <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>{bin.bin}</div>
                <div style={{ 
                  height: 20, 
                  backgroundColor: '#4A90E2', 
                  width: `${(bin.count / games.length) * 100}%`,
                  borderRadius: 2,
                }} />
                <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{bin.count}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Games Table */}
      <section className="section">
        <h2>Predicted Games</h2>
        {games.length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Game ID</th>
                <th>Team</th>
                <th>Team Total Line</th>
                <th>Pred Prob</th>
                <th>Confidence</th>
                <th>Side</th>
                <th>Hypothetical EV</th>
              </tr>
            </thead>
            <tbody>
              {games.map((game, i) => (
                <tr key={i}>
                  <td>{game.date || 'N/A'}</td>
                  <td>{game.game_id || 'N/A'}</td>
                  <td>{game.TEAM_ABBREVIATION || game.team_id || 'N/A'}</td>
                  <td>{game.TEAM_TOTAL_LINE?.toFixed(1) || 'N/A'}</td>
                  <td>{(game.p_hat * 100).toFixed(1)}%</td>
                  <td>{(game.confidence * 100).toFixed(1)}%</td>
                  <td style={{ 
                    fontWeight: 600,
                    color: game.recommended_side === 'OVER' ? '#2e7d32' : '#c62828'
                  }}>
                    {game.recommended_side}
                  </td>
                  <td style={{ 
                    color: game.hypothetical_ev && game.hypothetical_ev > 0 ? '#2e7d32' : '#c62828',
                    fontWeight: game.hypothetical_ev && game.hypothetical_ev > 0 ? 600 : 400
                  }}>
                    {game.hypothetical_ev !== undefined 
                      ? (game.hypothetical_ev > 0 ? '+' : '') + (game.hypothetical_ev * 100).toFixed(2) + '%'
                      : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No future games found. Make sure you have future games data loaded (see README).</p>
        )}
      </section>

      <div className="warning-box">
        <strong>⚠️ Important:</strong> These are model predictions for future games. Predictions use historical data for rolling features.
        Hypothetical EV assumes -110 odds (0.9091 payout). This is not a profitability claim.
      </div>
    </div>
  );
}
