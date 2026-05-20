import React, { useState, useRef, useEffect } from "react";
import type { TraceEvent } from "../types";

interface QAItem {
  question: string;
  answer: string;
  events: TraceEvent[];
  traceId: string;
}

const statusBadge: Record<string, React.CSSProperties> = {
  agent_think: { background: "#ede9fe", color: "#7c3aed" },
  tool_call: { background: "#fef3c7", color: "#d97706" },
  tool_result: { background: "#ecfdf5", color: "#065f46" },
  agent_answer: { background: "#dbeafe", color: "#1e40af" },
};

export default function QAPage() {
  const [qaList, setQaList] = useState<QAItem[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [qaList]);

  const handleAsk = async () => {
    if (!input.trim() || loading) return;
    const question = input.trim();
    setInput("");
    setLoading(true);

    const item: QAItem = { question, answer: "", events: [], traceId: "" };
    setQaList((prev) => [...prev, item]);

    try {
      const response = await fetch("http://localhost:8000/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await response.json();
      setQaList((prev) => prev.map((q) =>
        q.question === question
          ? { ...q, answer: data.answer || "未获取到答案" }
          : q
      ));
    } catch {
      setQaList((prev) => prev.map((q) =>
        q.question === question
          ? { ...q, answer: "请求失败" }
          : q
      ));
    }
    setLoading(false);
  };

  return (
    <div>
      {/* 标题 */}
      <div style={{ marginBottom: 28 }}>
        <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: "#1e293b" }}>💬 智能问答</h2>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#94a3b8" }}>基于已索引的文档内容回答问题</p>
      </div>

      {/* 对话列表 */}
      <div style={{ marginBottom: 20 }}>
        {qaList.length === 0 && (
          <div style={{ textAlign: "center", padding: 64, color: "#94a3b8" }}>
            <div style={{ fontSize: 48, marginBottom: 12 }}>💭</div>
            <div style={{ fontSize: 14 }}>在下方输入问题开始对话</div>
          </div>
        )}

        {qaList.map((qa, i) => (
          <div key={i} style={{ marginBottom: 24 }}>
            {/* 用户问题 */}
            <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
              <div style={{
                maxWidth: "80%", padding: "12px 18px", borderRadius: "16px 16px 4px 16px",
                background: "#4f46e5", color: "#fff", fontSize: 14, lineHeight: 1.6,
              }}>
                {qa.question}
              </div>
            </div>

            {/* AI 回答 */}
            <div style={{
              background: "#fff", borderRadius: 12, padding: 20,
              boxShadow: "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
              border: "1px solid #f1f5f9",
            }}>
              {/* 处理步骤 */}
              {qa.events.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: qa.answer ? 16 : 0 }}>
                  {qa.events.map((e, j) => {
                    const badge = statusBadge[e.event_type] || { background: "#f1f5f9", color: "#64748b" };
                    return (
                      <span key={j} style={{
                        fontSize: 11, padding: "3px 10px", borderRadius: 10, fontWeight: 500,
                        ...badge,
                      }}>
                        {e.event_type === "agent_think" ? "🤔 思考" :
                         e.event_type === "tool_call" ? "🔧 检索" :
                         e.event_type === "tool_result" ? "📄 结果" :
                         e.event_type === "agent_answer" ? "✅ 完成" :
                         e.event_type}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* 回答内容 */}
              {qa.answer ? (
                <div style={{ fontSize: 15, lineHeight: 1.9, color: "#334155", whiteSpace: "pre-wrap" }}>
                  {qa.answer}
                </div>
              ) : (
                <div style={{ fontSize: 14, color: "#94a3b8", display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                    background: "#4f46e5", animation: "pulse 1.4s infinite",
                  }} /> 思考中...
                </div>
              )}

              {/* Trace ID */}
              {qa.traceId && (
                <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid #f1f5f9", fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>
                  trace: {qa.traceId}
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* 输入栏 */}
      <div style={{
        display: "flex", gap: 10, padding: "16px 20px",
        background: "#fff", borderRadius: 14,
        boxShadow: "0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.04)",
        border: "1px solid #e2e8f0",
      }}>
        <input
          style={{
            flex: 1, padding: "12px 16px", border: "none", borderRadius: 10,
            fontSize: 14, background: "#f8fafc", outline: "none",
          }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          placeholder="输入问题，按 Enter 发送..."
          disabled={loading}
        />
        <button
          onClick={handleAsk}
          disabled={loading || !input.trim()}
          style={{
            padding: "10px 24px", background: loading || !input.trim() ? "#e2e8f0" : "#4f46e5",
            color: loading || !input.trim() ? "#94a3b8" : "#fff",
            border: "none", borderRadius: 10, cursor: loading || !input.trim() ? "not-allowed" : "pointer",
            fontSize: 14, fontWeight: 500, transition: "all 0.15s",
            display: "flex", alignItems: "center", gap: 6,
          }}
        >
          {loading ? "⏳ 思考中..." : "➤ 发送"}
        </button>
      </div>
    </div>
  );
}
