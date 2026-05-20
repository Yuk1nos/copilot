import React from "react";
import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import DocManager from "./pages/DocManager";
import QAPage from "./pages/QAPage";

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const loc = useLocation();
  const active = loc.pathname === to;
  return (
    <Link
      to={to}
      style={{
        display: "flex", alignItems: "center", gap: 10, padding: "10px 16px",
        borderRadius: 8, color: active ? "#eef2ff" : "#94a3b8",
        background: active ? "rgba(99,102,241,0.25)" : "transparent",
        textDecoration: "none", fontSize: 14, fontWeight: active ? 600 : 400,
        transition: "all 0.15s",
      }}
    >
      {children}
    </Link>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: "flex", minHeight: "100vh", background: "#f1f5f9" }}>
        <aside style={{
          width: 220, background: "#0f172a", color: "#e2e8f0",
          padding: "24px 12px", display: "flex", flexDirection: "column", gap: 4,
        }}>
          <div style={{ padding: "0 16px 24px" }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: "#eef2ff", letterSpacing: -0.5 }}>
              📋 Copilot
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>企业文档助手</div>
          </div>

          <NavLink to="/">📄 文档管理 &amp; 摘要</NavLink>
          <NavLink to="/ask">💬 智能问答</NavLink>

          <div style={{ marginTop: "auto", padding: "16px", fontSize: 11, color: "#475569" }}>
            v1.0 · MVP
          </div>
        </aside>

        <main style={{ flex: 1, padding: "32px 40px", maxWidth: 1100 }}>
          <Routes>
            <Route path="/" element={<DocManager />} />
            <Route path="/ask" element={<QAPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
