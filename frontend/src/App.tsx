import { NavLink, Route, Routes } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Products from './pages/Products';
import ProductDetail from './pages/ProductDetail';
import ComparisonPage from './pages/Comparison';
import Disclaimer from './components/Disclaimer';

export default function App() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <span className="logo">🏷️ LabelWatch India</span>
          <nav>
            <NavLink to="/" end>Dashboard</NavLink>
            <NavLink to="/products">Products</NavLink>
          </nav>
        </div>
      </header>
      <main className="layout">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:id" element={<ProductDetail />} />
          <Route path="/comparisons/:id" element={<ComparisonPage />} />
        </Routes>
        <Disclaimer />
      </main>
    </>
  );
}
