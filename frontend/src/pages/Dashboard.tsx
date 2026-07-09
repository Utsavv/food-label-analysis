import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, DashboardStats, Product, ScrapeRun } from '../api/client';
import SignificanceBadge from '../components/SignificanceBadge';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [failedRuns, setFailedRuns] = useState<ScrapeRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.dashboardStats(), api.listProducts(), api.listRuns({ status: 'failed' })])
      .then(([s, p, r]) => {
        setStats(s);
        setProducts(p);
        setFailedRuns(r);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      {error && <div className="error-box">{error} — is the backend running?</div>}

      <div className="stat-grid">
        <div className="card stat">
          <div className="value">{stats?.tracked_products ?? '—'}</div>
          <div className="label">Tracked products</div>
        </div>
        <div className="card stat">
          <div className="value">{stats?.changed_this_week ?? '—'}</div>
          <div className="label">Products changed this week</div>
        </div>
        <div className="card stat warn">
          <div className="value">{stats?.high_significance_changes ?? '—'}</div>
          <div className="label">High-significance changes (7d)</div>
        </div>
        <div className="card stat danger">
          <div className="value">{stats?.failed_runs_this_week ?? '—'}</div>
          <div className="label">Failed scrape runs (7d)</div>
        </div>
      </div>

      <h2>Products</h2>
      <div className="card">
        {products.length === 0 ? (
          <p className="muted">
            No products yet. <Link to="/products">Add one</Link> or run the seed script for demo data.
          </p>
        ) : (
          <table>
            <thead>
              <tr><th>Product</th><th>Category</th><th>Last change significance</th><th>Last version</th></tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/products/${p.id}`}>{p.brand} {p.name}</Link></td>
                  <td>{p.category.replace(/_/g, ' ')}</td>
                  <td><SignificanceBadge score={p.latest_significance} /></td>
                  <td className="muted">
                    {p.latest_version_at ? new Date(p.latest_version_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {failedRuns.length > 0 && (
        <>
          <h2>Failed scrape runs</h2>
          <div className="card">
            <table>
              <thead><tr><th>Run</th><th>Product</th><th>Error</th><th>When</th></tr></thead>
              <tbody>
                {failedRuns.slice(0, 10).map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td><Link to={`/products/${r.product_id}`}>product {r.product_id}</Link></td>
                    <td className="muted">{r.error_message}</td>
                    <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
