import { useState } from 'react';
import { StructuredLabel } from '../api/client';
import IngredientPanel from './IngredientPanel';

export default function LabelSummary({
  label,
  category,
}: {
  label: StructuredLabel;
  category: string;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div>
      <div className="flex" style={{ flexWrap: 'wrap', gap: 18 }}>
        <span className="muted">Serving: <strong>{label.serving_size.value ?? 'not found on label/source'}</strong></span>
        <span className="muted">FSSAI: <strong className="mono">{label.fssai_license.value ?? 'not found'}</strong></span>
        <span className="muted">
          Veg mark:{' '}
          <strong>
            {label.veg_status.value === 'vegetarian' ? '🟢 Vegetarian'
              : label.veg_status.value === 'non_vegetarian' ? '🔴 Non-vegetarian'
              : 'not found'}
          </strong>
        </span>
      </div>

      <h3>Nutrition (per serving)</h3>
      <table>
        <thead>
          <tr><th>Nutrient</th><th>Amount</th></tr>
        </thead>
        <tbody>
          {label.nutrition.map((n) => (
            <tr key={n.name}>
              <td>{n.name.replace(/_/g, ' ')}</td>
              <td>{n.amount != null ? `${n.amount} ${n.unit ?? ''}` : 'not found on label/source'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Ingredients <span className="muted">(click any for a plain-English explanation)</span></h3>
      <div>
        {label.ingredients.map((ing) => (
          <span
            key={ing.position}
            className={`chip ${ing.is_sweetener || ing.is_preservative ? 'flag' : ''}`}
            onClick={() => setSelected(ing.name_normalized)}
            title={ing.is_sweetener ? 'Sweetener' : ing.is_preservative ? 'Preservative' : ing.is_additive ? 'Additive' : ''}
          >
            {ing.position}. {ing.name_raw}
            {ing.is_sweetener ? ' 🍬' : ing.is_preservative ? ' 🧴' : ''}
          </span>
        ))}
        {label.ingredients.length === 0 && <p className="muted">not found on label/source</p>}
      </div>

      <h3>Allergens</h3>
      <p>
        {label.allergens.length > 0
          ? label.allergens.map((a) => (
              <span key={`${a.name}-${a.presence_type}`} className="chip flag">
                {a.name} ({a.presence_type.replace('_', ' ')})
              </span>
            ))
          : <span className="muted">not found on label/source</span>}
      </p>

      <h3>Certifications & claims</h3>
      <p>
        {label.certifications.map((c) => <span key={c} className="chip">✔ {c}</span>)}
        {label.claims.map((c) => <span key={c.normalized_claim} className="chip">“{c.claim_text}”</span>)}
      </p>

      {label.warnings.length > 0 && (
        <>
          <h3>Warnings</h3>
          <ul className="clean">{label.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </>
      )}

      {selected && (
        <IngredientPanel ingredient={selected} category={category} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
