import React, { useEffect, useState, useCallback } from "react";
import type { DocumentInfo, TraceEvent } from "../types";
import { fetchDocuments } from "../api/client";

const card: React.CSSProperties = {
  background: "#fff", borderRadius: 12, padding: 24,
  boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
  marginBottom: 24,
};

const btnPrimary: React.CSSProperties = {
  padding: "10px 20px", background: "#4f46e5", color: "#fff",
  border: "none", borderRadius: 8, cursor: "pointer",
  fontSize: 14, fontWeight: 500, transition: "background 0.15s",
};

const btnDanger: React.CSSProperties = {
  padding: "5px 10px", background: "#fef2f2", color: "#ef4444",
  border: "1px solid #fecaca", borderRadius: 6, cursor: "pointer",
  fontSize: 12, fontWeight: 500,
};

export default function DocManager() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [uploading, setUploading] = useState(false);

  const loadDocs = useCallback(() => { fetchDocuments().then(setDocs); }, []);
  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleDelete = async (docId: string) => {
    if (!confirm("确定删除此文档？")) return;
    setDocs((prev) => prev.filter((d) => d.id !== docId));
    try {
      const res = await fetch(`http://localhost:8000/api/documents/${docId}`, { method: "DELETE" });
      if (!res.ok) loadDocs();
    } catch { loadDocs(); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setEvents([]);
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch("http://localhost:8000/api/upload", { method: "POST", body: formData });
    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const normalized = buffer.replace(/\r\n/g, "\n");
      const lines = normalized.split("\n\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const event: TraceEvent = JSON.parse(line.slice(6));
          setEvents((prev) => [...prev, event]);
          if (event.event_type === "doc_indexed") {
            setUploading(false);
            loadDocs();
          }
        }
      }
    }
  };

  const [selected, setSelected] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [summarizing, setSummarizing] = useState(false);

  const toggleSelect = (docId: string) => {
    setSelected((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const toggleAll = () => {
    setSelected(selected.length === docs.length ? [] : docs.map((d) => d.id));
  };

  const handleGenerateSummary = async () => {
    setSummarizing(true);
    setSummary("");
    try {
      const response = await fetch("http://localhost:8000/api/summary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: selected.length ? selected : null }),
      });
      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const normalized = buffer.replace(/\r\n/g, "\n");
        const lines = normalized.split("\n\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const event: TraceEvent = JSON.parse(line.slice(6));
            if (event.event_type === "summary_done") {
              setSummary(String((event.output as Record<string, unknown>).summary || ""));
              setSummarizing(false);
            }
          }
        }
      }
    } catch { setSummarizing(false); }
  };

  const indexedDocs = docs.filter((d) => d.status === "indexed");
  const statusColor = (s: string) => s === "indexed" ? "#10b981" : s === "error" ? "#ef4444" : "#f59e0b";

  return (
    <div>
      {/* 文档管理卡片 */}
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#1e293b" }}>📄 文档管理</h2>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>上传、管理和选择文档生成摘要</p>
          </div>
          <label style={{
            ...btnPrimary, display: "inline-flex", alignItems: "center", gap: 6,
            cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.6 : 1,
          }}>
            {uploading ? "⏳ 处理中..." : "+ 上传文档"}
            <input type="file" hidden onChange={handleUpload} accept=".pdf,.docx,.txt,.md" disabled={uploading} />
          </label>
        </div>

        {events.length > 0 && (
          <div style={{ marginBottom: 16, padding: "12px 16px", background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#64748b", marginBottom: 6 }}>处理进度</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {events.map((e, i) => (
                <span key={i} style={{
                  fontSize: 11, padding: "2px 8px", borderRadius: 12,
                  background: e.status === "done" ? "#ecfdf5" : e.status === "error" ? "#fef2f2" : "#fefce8",
                  color: e.status === "done" ? "#065f46" : e.status === "error" ? "#991b1b" : "#92400e",
                }}>
                  {e.event_type}
                </span>
              ))}
            </div>
          </div>
        )}

        {docs.length === 0 ? (
          <div style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
            <div style={{ fontSize: 14 }}>暂无文档，点击上方按钮上传</div>
          </div>
        ) : (
          <div>
            <div style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 12, fontSize: 13 }}>
              <span style={{ color: "#64748b" }}>点击文件名选择要摘要的文档：</span>
              <button onClick={toggleAll} style={{
                padding: "3px 10px", background: "#f1f5f9", border: "1px solid #e2e8f0",
                borderRadius: 6, cursor: "pointer", fontSize: 12, color: "#475569",
              }}>
                {selected.length === docs.length ? "取消全选" : "全选"}
              </button>
              {selected.length > 0 && (
                <span style={{ color: "#4f46e5", fontWeight: 500 }}>已选 {selected.length} 篇</span>
              )}
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e2e8f0" }}>
                  <th style={{ textAlign: "left", padding: "10px 12px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>文件名</th>
                  <th style={{ textAlign: "left", padding: "10px 12px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>字数</th>
                  <th style={{ textAlign: "left", padding: "10px 12px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>片段</th>
                  <th style={{ textAlign: "left", padding: "10px 12px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>状态</th>
                  <th style={{ textAlign: "left", padding: "10px 12px", fontSize: 12, fontWeight: 600, color: "#64748b" }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => {
                  const isSelected = selected.includes(d.id);
                  return (
                    <tr key={d.id} style={{
                      borderBottom: "1px solid #f1f5f9",
                      background: isSelected ? "#eef2ff" : "transparent",
                      transition: "background 0.1s",
                    }}>
                      <td
                        onClick={() => toggleSelect(d.id)}
                        style={{
                          padding: "10px 12px", cursor: "pointer", color: "#4f46e5",
                          fontWeight: isSelected ? 600 : 400, fontSize: 14,
                        }}
                      >
                        <span style={{ marginRight: 6, opacity: isSelected ? 1 : 0.3 }}>
                          {isSelected ? "●" : "○"}
                        </span>
                        {d.filename}
                      </td>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "#64748b" }}>{d.char_count.toLocaleString()}</td>
                      <td style={{ padding: "10px 12px", fontSize: 13, color: "#64748b" }}>{d.chunk_count}</td>
                      <td style={{ padding: "10px 12px" }}>
                        <span style={{
                          fontSize: 11, padding: "2px 8px", borderRadius: 10,
                          background: d.status === "indexed" ? "#ecfdf5" : d.status === "error" ? "#fef2f2" : "#fefce8",
                          color: statusColor(d.status),
                        }}>
                          {d.status}
                        </span>
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        <button onClick={() => handleDelete(d.id)} style={btnDanger}>删除</button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 摘要卡片 */}
      <div style={card}>
        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: "#1e293b" }}>📝 结构化摘要</h2>
        <p style={{ margin: "0 0 20px", fontSize: 13, color: "#94a3b8" }}>
          {indexedDocs.length === 0 ? "请先上传并索引文档" : `共 ${indexedDocs.length} 篇可摘要文档`}
        </p>

        <button
          onClick={handleGenerateSummary}
          disabled={summarizing || indexedDocs.length === 0}
          style={{
            ...btnPrimary,
            opacity: summarizing || indexedDocs.length === 0 ? 0.5 : 1,
            cursor: summarizing || indexedDocs.length === 0 ? "not-allowed" : "pointer",
          }}
        >
          {summarizing ? "⏳ 生成中..." : selected.length > 0 ? `✨ 为已选 ${selected.length} 篇生成摘要` : "📋 为全部文档生成摘要"}
        </button>

        {summary && (
          <div style={{
            marginTop: 20, lineHeight: 1.9, fontSize: 15, color: "#334155",
            background: "#f8fafc", padding: "20px 24px", borderRadius: 10,
            border: "1px solid #e2e8f0", whiteSpace: "pre-wrap",
          }}>
            {summary}
          </div>
        )}
      </div>
    </div>
  );
}
