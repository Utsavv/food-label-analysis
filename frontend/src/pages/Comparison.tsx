import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, Comparison, DiffItem, LabelVersion } from '../api/client';
import SignificanceBadge from '../components/SignificanceBadge';

const AUDIENCE_LABELS: Record<string, string> = {
  general_consumers: 'General consumers',
  fitness_users: 'Fitness users',
  sugar_watchers: 'People monitoring sugar',
  sodium_hypertension_watchers: 'People monitoring sodium / blood pressure',
  allergy_sufferers: 'People with allergies',
  vegetarians_vegans: 'Vegetarians & vegans',
  caffeine_sweetener_sensitive: 'Sensitive to caffeine / artificial sweeteners',
};

function DiffSection({ title, items }: { title: string; items: DiffItem[] }) {
  if (items.length === 0) return null;
  return (
    <>
      <h3>{title}</h3>
      <table>
        <thead><tr><th>Change</th><th>Old</th><th>New</th><th>Significance</th></tr></thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx}>
              <td>{item.detail}</td>
              <td className="diff-old">{item.old_value != null ? `${item.old_value} ${item.unit ?? ''}` : '—'}</td>
              <td className="diff-new">
                {item.new_value != null ? `${item.new_value} ${item.unit ?? ''}` : '—'}
                {item.percent_change != null && (
                  <span className="muted"> ({item.percent_change > 0 ? '+' : ''}{item.percent_change}%)</span>
                )}
              </td>
              <td><SignificanceBadge score={item.significance} level={item.significance_level} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

export default function ComparisonPage() {
  const { id } = useParams();
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [oldVersion, setOldVersion] = useState<LabelVersion | null>(null);
  const [newVersion, setNewVersion] = useState<LabelVersion | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getComparison(Number(id))
      .then(async (c) => {
        setComparison(c);
        const [oldV, newV] = await Promise.all([
          api.getVersion(c.old_label_version_id),
          api.getVersion(c.new_label_version_id),
        ]);
        setOldVersion(oldV);
        setNewVersion(newV);
      })
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <div className="error-box">{error}</div>;
  if (!comparison) return <p className="muted">Loading comparison…</p>;

  const items = comparison.diff_json.items;
  const nutrition = items.filter((i) => i.type.startsWith('nutrient_') || i.type === 'serving_size_changed');
  const ingredients = items.filter((i) => i.type.startsWith('ingredient_'));
  const allergens = items.filter((i) => i.type.startsWith('allergen_'));
  const certifications = items.filter((i) => i.type.startsWith('certification_'));
  const other = items.filter(
    (i) => !nutrition.includes(i) && !ingredients.includes(i) && !allergens.includes(i) && !certifications.includes(i),
  );

  const changeAnalysis = comparison.analyses.find((a) => a.analysis_type === 'change_analysis');
  const healthContext = comparison.analyses.find((a) => a.analysis_type === 'health_context');
  const report = changeAnalysis?.analysis_json as
    | { summary?: string; what_changed?: string[]; why_it_matters?: string[]; who_should_care?: string[] }
    | undefined;
  const health = healthContext?.analysis_json as
    | { by_audience?: Record<string, string[]> }
    | undefined;

  return (
    <div>
      <p><Link to={`/products/${comparison.product_id}`}>← Back to product</Link></p>
      <div className="flex between">
        <h1>
          Label comparison: v{oldVersion?.version_number ?? '…'} → v{newVersion?.version_number ?? '…'}
        </h1>
        <SignificanceBadge
          score={comparison.significance_score}
          level={comparison.diff_json.overall_level}
        />
      </div>
      <p className="muted">
        {oldVersion && newVersion && (
          <>
            {new Date(oldVersion.effective_detected_at).toLocaleDateString()} →{' '}
            {new Date(newVersion.effective_detected_at).toLocaleDateString()} · {items.length} change(s)
          </>
        )}
      </p>

      {changeAnalysis && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>🤖 What changed, in plain English</h2>
          <p><strong>{report?.summary ?? changeAnalysis.plain_english_summary}</strong></p>
          {report?.why_it_matters && (
            <>
              <h3>Why it matters</h3>
              <ul className="clean">{report.why_it_matters.map((w) => <li key={w}>{w}</li>)}</ul>
            </>
          )}
          {report?.who_should_care && (
            <>
              <h3>Who should care</h3>
              <p>{report.who_should_care.map((w) => <span key={w} className="chip flag">{w}</span>)}</p>
            </>
          )}
          <p className="muted">
            {changeAnalysis.model_name} · prompt {changeAnalysis.prompt_version} · confidence{' '}
            {(changeAnalysis.confidence_score * 100).toFixed(0)}%
          </p>
        </div>
      )}

      {health?.by_audience && Object.keys(health.by_audience).length > 0 && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>🩺 Health context by audience</h2>
          {Object.entries(health.by_audience).map(([audience, statements]) => (
            <div key={audience}>
              <h3>{AUDIENCE_LABELS[audience] ?? audience}</h3>
              <ul className="clean">{statements.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Detailed diff</h2>
        <DiffSection title="Nutrition & serving size" items={nutrition} />
        <DiffSection title="Ingredients" items={ingredients} />
        <DiffSection title="Allergens" items={allergens} />
        <DiffSection title="Certifications" items={certifications} />
        <DiffSection title="Claims, warnings & other" items={other} />
        {items.length === 0 && <p className="muted">No structured differences.</p>}
      </div>

      {oldVersion && newVersion && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Original evidence</h2>
          <div className="form-grid">
            <div>
              <h3>Old label (v{oldVersion.version_number})</h3>
              <pre className="rawtext">{oldVersion.raw_text}</pre>
            </div>
            <div>
              <h3>New label (v{newVersion.version_number})</h3>
              <pre className="rawtext">{newVersion.raw_text}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
