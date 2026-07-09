import { FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, Product } from '../api/client';
import SignificanceBadge from '../components/SignificanceBadge';

const CATEGORIES = [
  { value: 'protein_powder', label: 'Protein powder' },
  { value: 'protein_bar', label: 'Protein bar' },
  { value: 'other', label: 'Other packaged food' },
];

export default function Products() {
  const [products, setProducts] = useState<Product[]>([]);
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listProducts({
        ...(category ? { category } : {}),
        ...(status ? { status } : {}),
      })
      .then(setProducts)
      .catch((e: Error) => setError(e.message));
  }, [category, status]);

  useEffect(load, [load]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const data = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      brand: data.get('brand'),
      name: data.get('name'),
      category: data.get('category'),
      notes: data.get('notes') || null,
    };
    const url = data.get('source_url');
    if (url) {
      body.source_url = url;
      body.source_type = data.get('source_type');
    }
    try {
      const product = await api.createProduct(body);
      setNotice(`Added ${product.brand} ${product.name}.`);
      setShowForm(false);
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div>
      <div className="flex between">
        <h1>Products</h1>
        <button onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : '+ Add product'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {notice && <div className="success-box">{notice}</div>}

      {showForm && (
        <form className="card" onSubmit={handleSubmit}>
          <div className="form-grid">
            <div>
              <label htmlFor="brand">Brand</label>
              <input id="brand" name="brand" required placeholder="e.g. MaxFit" />
            </div>
            <div>
              <label htmlFor="name">Product name</label>
              <input id="name" name="name" required placeholder="e.g. Whey Gold Chocolate 1kg" />
            </div>
            <div>
              <label htmlFor="category">Category</label>
              <select id="category" name="category" defaultValue="protein_powder">
                {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="source_type">Source type</label>
              <select id="source_type" name="source_type" defaultValue="manufacturer">
                <option value="manufacturer">Manufacturer website</option>
                <option value="mock">Mock (demo fixture)</option>
              </select>
            </div>
            <div className="full">
              <label htmlFor="source_url">Manufacturer source URL (optional)</label>
              <input id="source_url" name="source_url" type="url" placeholder="https://brand.com/products/item" />
            </div>
            <div className="full">
              <label htmlFor="notes">Notes (optional)</label>
              <textarea id="notes" name="notes" rows={2} />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <button type="submit">Create product</button>
          </div>
        </form>
      )}

      <div className="card">
        <div className="flex" style={{ marginBottom: 12 }}>
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 180 }}>
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        <table>
          <thead>
            <tr><th>Product</th><th>Category</th><th>Status</th><th>Sources</th><th>Last change</th></tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td><Link to={`/products/${p.id}`}>{p.brand} {p.name}</Link></td>
                <td>{p.category.replace(/_/g, ' ')}</td>
                <td><span className={`badge ${p.status === 'active' ? 'ok' : 'neutral'}`}>{p.status}</span></td>
                <td className="muted">{p.sources.length}</td>
                <td><SignificanceBadge score={p.latest_significance} /></td>
              </tr>
            ))}
            {products.length === 0 && (
              <tr><td colSpan={5} className="muted">No products match the filter.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
