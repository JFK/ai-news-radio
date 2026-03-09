import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Dashboard from "./components/Dashboard";
import EpisodeDetail from "./components/EpisodeDetail";
import CostDashboard from "./components/CostDashboard";
import Settings from "./components/Settings";
import LanguageSwitcher from "./components/LanguageSwitcher";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const { pathname } = useLocation();
  const isActive = to === "/" ? pathname === "/" : pathname.startsWith(to);
  return (
    <Link
      to={to}
      className={`text-sm font-medium px-3 py-1 rounded-md transition-colors ${
        isActive
          ? "bg-blue-100 text-blue-700"
          : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
      }`}
    >
      {children}
    </Link>
  );
}

function App() {
  const { t } = useTranslation();

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <Link to="/" className="text-2xl font-bold text-gray-900">
              {t("app.title")}
            </Link>
            <div className="flex items-center gap-4">
              <nav className="flex gap-2">
                <NavLink to="/">{t("nav.dashboard")}</NavLink>
                <NavLink to="/costs">{t("nav.costs")}</NavLink>
                <NavLink to="/settings">{t("nav.settings")}</NavLink>
              </nav>
              <LanguageSwitcher />
            </div>
          </div>
        </header>
        <main className="max-w-7xl mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/episodes/:id" element={<EpisodeDetail />} />
            <Route path="/costs" element={<CostDashboard />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
