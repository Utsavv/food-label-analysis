import { render, screen } from '@testing-library/react';
import SignificanceBadge, { levelFor } from './SignificanceBadge';

describe('levelFor', () => {
  it('maps scores to levels', () => {
    expect(levelFor(95)).toBe('very_high');
    expect(levelFor(65)).toBe('high');
    expect(levelFor(40)).toBe('medium');
    expect(levelFor(15)).toBe('low');
    expect(levelFor(2)).toBe('minimal');
  });
});

describe('SignificanceBadge', () => {
  it('renders score and level', () => {
    render(<SignificanceBadge score={95.8} />);
    expect(screen.getByText(/Very high/)).toBeTruthy();
    expect(screen.getByText(/96/)).toBeTruthy();
  });

  it('renders placeholder when no score', () => {
    render(<SignificanceBadge score={null} />);
    expect(screen.getByText('—')).toBeTruthy();
  });
});
