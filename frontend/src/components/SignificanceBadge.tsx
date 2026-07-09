export function levelFor(score: number): string {
  if (score >= 80) return 'very_high';
  if (score >= 60) return 'high';
  if (score >= 35) return 'medium';
  if (score >= 10) return 'low';
  return 'minimal';
}

const LABELS: Record<string, string> = {
  very_high: 'Very high',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  minimal: 'Minimal',
  none: 'None',
};

export default function SignificanceBadge({
  score,
  level,
}: {
  score?: number | null;
  level?: string;
}) {
  if (score == null && !level) return <span className="badge none">—</span>;
  const resolved = level ?? levelFor(score ?? 0);
  return (
    <span className={`badge ${resolved}`} title={score != null ? `${score}/100` : undefined}>
      {LABELS[resolved] ?? resolved}
      {score != null ? ` · ${Math.round(score)}` : ''}
    </span>
  );
}
