import { useEffect, useState } from 'react';
import { api, IngredientExplanation } from '../api/client';

interface Props {
  ingredient: string;
  category: string;
  onClose: () => void;
}

export default function IngredientPanel({ ingredient, category, onClose }: Props) {
  const [explanation, setExplanation] = useState<IngredientExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setExplanation(null);
    setError(null);
    api
      .explainIngredient(ingredient, category)
      .then(setExplanation)
      .catch((e: Error) => setError(e.message));
  }, [ingredient, category]);

  return (
    <div className="panel-overlay" onClick={onClose}>
      <aside className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="flex between">
          <h2 style={{ margin: 0 }}>🧪 {ingredient}</h2>
          <button className="secondary" onClick={onClose}>Close</button>
        </div>
        {error && <div className="error-box">{error}</div>}
        {!explanation && !error && <p className="muted">Looking up ingredient…</p>}
        {explanation && (
          <>
            <h3>What it is</h3>
            <p>{explanation.plain_english_meaning}</p>
            <h3>Why it's used</h3>
            <p>{explanation.common_use}</p>
            <h3>How common it is</h3>
            <p>{explanation.commonness}</p>
            <h3>Health context</h3>
            <p>{explanation.health_context}</p>
            <p className="muted">
              Confidence: {(explanation.confidence * 100).toFixed(0)}% · {explanation.model_name} ·
              prompt {explanation.prompt_version}
            </p>
          </>
        )}
      </aside>
    </div>
  );
}
