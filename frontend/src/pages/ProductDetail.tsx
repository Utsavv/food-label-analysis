import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  api,
  CheckNowResult,
  Comparison,
  LabelVersion,
  LabelVersionSummary,
  Product,
} from '../api/client';
import LabelSummary from '../components/LabelSummary';
import SignificanceBadge from '../components/SignificanceBadge';

export default function ProductDetail() {
  const { id } = useParams();
  const productId = Number(id);

  const [product, setProduct] = useState<Product | null>(null);
  const [versions, setVersions] = useState<LabelVersionSummary[]>([]);
  const [latest, setLatest] = useState<LabelVersion | null>(null);
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<CheckNowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, v, c] = await Promise.all([
        api.getProduct(productId),
        api.listVersions(productId),
        api.listComparisons(productId),
      ]);
      setProduct(p);
      setVersions(v);
      setComparisons(c);
      if (v.length > 0) setLatest(await api.getVersion(v[0].id));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [productId]);

  useEffect(() => {
    load();
  }, [load]);

  async function runCheckNow() {
    setChecking(true);
    setCheckResult(null);
    try {
      const result = await api.checkNow(productId);
      setCheckResult(result);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChecking(false);
    }
  }

  if (!product) {
    return error ? <div className="error-box">{error}</div> : <p className="muted">Loading…</p>;
  }

  const latestAnalysis = comparisons[0]?.analyses.find((a) => a.analysis_type === 'change_analysis');

  return (
    <div>
      <div className="flex between">
        <h1>{product.brand} {product.name}</h1>
        <button onClick={runCheckNow} disabled={checking}>
          {checking ? 'Checking…' : '▶ Run check now'}
        </button>
      </div>
      <p className="muted">
        {product.category.replace(/_/g, ' ')} · {product.country} ·{' '}
        <span className={`badge ${product.status === 'active' ? 'ok' : 'neutral'}`}>{product.status}</span>
        {product.notes ? <> · {product.notes}</> : null}
      </p>

      {error && <div className="error-box">{error}</div>}
      {checkResult && (
        <div className={checkResult.status === 'failed' ? 'error-box' : 'success-box'}>
          {checkResult.message}{' '}
          {checkResult.comparison_id && (
            <Link to={`/comparisons/${checkResult.comparison_id}`}>View comparison →</Link>
          )}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Sources</h2>
        <table>
          <thead><tr><th>Type</th><th>URL</th><th>Frequency</th><th>Last checked</th></tr></thead>
          <tbody>
            {product.sources.map((s) => (
              <tr key={s.id}>
                <td><span className="badge neutral">{s.source_type}</span></td>
                <td className="mono">{s.source_url}</td>
                <td>{s.scrape_frequency}</td>
                <td className="muted">{s.last_checked_at ? new Date(s.last_checked_at).toLocaleString() : 'never'}</td>
              </tr>
            ))}
            {product.sources.length === 0 && (
              <tr><td colSpan={4} className="muted">No sources configured — add one via the API.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {latestAnalysis && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Latest AI analysis</h2>
          <p>{latestAnalysis.plain_english_summary}</p>
          <p className="muted">
            {latestAnalysis.model_name} · prompt {latestAnalysis.prompt_version} ·{' '}
            {new Date(latestAnalysis.created_at).toLocaleString()} ·{' '}
            <Link to={`/comparisons/${comparisons[0].id}`}>Full comparison →</Link>
          </p>
        </div>
      )}

      {latest && (
        <div className="card">
          <div className="flex between">
            <h2 style={{ marginTop: 0 }}>
              Current label (v{latest.version_number})
              <span className="muted"> · confidence {(latest.confidence_score * 100).toFixed(0)}%</span>
            </h2>
            <button className="secondary" onClick={() => setShowRaw((v) => !v)}>
              {showRaw ? 'Hide evidence' : 'Show original evidence'}
            </button>
          </div>
          {showRaw && <pre className="rawtext">{latest.raw_text}</pre>}
          <LabelSummary label={latest.structured_json} category={product.category} />
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Version history & change timeline</h2>
        <table>
          <thead>
            <tr><th>Version</th><th>Detected</th><th>Hash</th><th>Confidence</th></tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.id}>
                <td>v{v.version_number}</td>
                <td>{new Date(v.effective_detected_at).toLocaleString()}</td>
                <td className="mono">{v.version_hash.slice(0, 12)}…</td>
                <td>{(v.confidence_score * 100).toFixed(0)}%</td>
              </tr>
            ))}
            {versions.length === 0 && (
              <tr><td colSpan={4} className="muted">No label versions yet — run a check.</td></tr>
            )}
          </tbody>
        </table>

        {comparisons.length > 0 && (
          <>
            <h3>Comparisons</h3>
            <table>
              <thead><tr><th>When</th><th>Versions</th><th>Significance</th><th></th></tr></thead>
              <tbody>
                {comparisons.map((c) => (
                  <tr key={c.id}>
                    <td>{new Date(c.created_at).toLocaleString()}</td>
                    <td>#{c.old_label_version_id} → #{c.new_label_version_id}</td>
                    <td><SignificanceBadge score={c.significance_score} level={c.diff_json.overall_level} /></td>
                    <td><Link to={`/comparisons/${c.id}`}>View →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}
