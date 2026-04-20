import { Routes, Route, NavLink } from "react-router-dom";
import { Shield, BarChart3, Settings as SettingsIcon, Activity } from "lucide-react";
import Dashboard from "./pages/Dashboard";
import CaseDetail from "./pages/CaseDetail";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";

const navItems = [
  { to: "/", label: "Dashboard", icon: Activity },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col">
        <div className="p-4 flex items-center gap-2 border-b border-gray-700">
          <Shield className="w-6 h-6 text-green-400" />
          <span className="font-bold text-white text-sm">AllGreen Fraud</span>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded text-sm ${
                  isActive
                    ? "bg-gray-800 text-white"
                    : "hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 text-xs text-gray-500 border-t border-gray-700">
          v0.1.0 — Phase 5
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}
