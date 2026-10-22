import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FALLBACK = "I am sorry, but the provided documents do not contain enough information to answer this question.";

export default function App() {
  const [theme, setTheme] = useState(() => {
    const savedTheme = window.localStorage.getItem("knowledge-studio-theme");
    if (savedTheme === "light" || savedTheme === "dark") return savedTheme;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState([]);
  const bottomRef = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("knowledge-studio-theme", theme);
  }, [theme]);

  async function refreshDocuments() {
    try {
      const res = await fetch(`${API}/documents`);
      if (!res.ok) throw new Error("Could not load document list.");
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (e) { setNotice(e.message); }
  }
  useEffect(() => { refreshDocuments(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function upload() {
    if (!file) return setNotice("Choose a PDF or TXT file first.");
    setUploading(true); setNotice("");
    try {
      const body = new FormData(); body.append("file", file);
      const res = await fetch(`${API}/upload`, { method: "POST", body });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed.");
      setNotice(`${data.document_name} indexed into ${data.chunk_count} chunks.`);
      setFile(null);
      await refreshDocuments();
      setSelectedDocument(data.document_name);
    } catch (e) { setNotice(e.message); }
    finally { setUploading(false); }
  }

  async function ask(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q || asking) return;
    setQuestion(""); setAsking(true); setNotice("");
    setMessages(prev => [...prev, { role: "user", text: q }]);
    try {
      const res = await fetch(`${API}/query`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, document_name: selectedDocument || null })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Query failed.");
      setMessages(prev => [...prev, { role: "assistant", text: data.answer, sources: data.sources || [], grounded: data.grounded }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "error", text: e.message }]);
    } finally { setAsking(false); }
  }

  async function removeDocument(name) {
    if (!window.confirm(`Delete ${name} and its indexed chunks?`)) return;
    try {
      const res = await fetch(`${API}/documents/${encodeURIComponent(name)}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Delete failed.");
      setNotice(data.message);
      if (selectedDocument === name) setSelectedDocument("");
      await refreshDocuments();
    } catch (e) { setNotice(e.message); }
  }

  const totalChunks = documents.reduce((total, document) => total + document.chunk_count, 0);

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand-mark" aria-hidden="true"><span>K</span><i /></div>
      <div className="brand-copy">
        <div className="eyebrow">ENTERPRISE AI · WORKSPACE</div>
        <h1>Knowledge Studio</h1>
      </div>
      <div className="topbar-spacer" />
      <button
        className="theme-toggle"
        type="button"
        onClick={() => setTheme(currentTheme => currentTheme === "dark" ? "light" : "dark")}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      >
        {theme === "dark"
          ? <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" /></svg>
          : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.2 15.2A8.5 8.5 0 0 1 8.8 3.8 8.5 8.5 0 1 0 20.2 15.2Z" /></svg>}
      </button>
      <div className="status"><span /> All systems ready</div>
      <div className="topbar-divider" />
      <div className="profile-mark" title="Your workspace">KS</div>
    </header>
    <main className="layout">
      <aside className="sidebar">
        <div className="sidebar-heading">
          <div className="section-title">YOUR LIBRARY</div>
          <button className="icon-button" title="Refresh document list" aria-label="Refresh document list" onClick={refreshDocuments}>↻</button>
        </div>
        <div className="library-summary">
          <div className="library-summary-icon">✳</div>
          <div><strong>{documents.length} {documents.length === 1 ? "document" : "documents"}</strong><span>{totalChunks} searchable sections</span></div>
          <span className="library-pulse" />
        </div>
        <label className={`upload-zone ${file ? "has-file" : ""}`}>
          <input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={e => setFile(e.target.files?.[0] || null)} />
          <span className="upload-icon">{file ? "✓" : "+"}</span>
          <strong>{file ? file.name : "Add to your library"}</strong>
          <small>{file ? "Ready to index" : "Drop a file or browse"}</small>
          <span className="upload-formats">PDF <i /> TXT <i /> MAX 15 MB</span>
        </label>
        <button className="primary full" onClick={upload} disabled={uploading || !file}>
          {uploading ? <><span className="button-spinner" /> Indexing…</> : <>Upload document <span>↗</span></>}
        </button>
        <div className="list-heading"><span>Indexed documents</span><span className="count">{documents.length}</span></div>
        <div className="document-list">
          {documents.length === 0 && <p className="muted small">Your uploaded documents will appear here.</p>}
          {documents.map(doc => <div className={`doc-row ${selectedDocument === doc.document_name ? "selected" : ""}`} key={doc.document_name}>
            <button className="doc-select" onClick={() => setSelectedDocument(selectedDocument === doc.document_name ? "" : doc.document_name)} title="Filter questions to this document">
              <span className="file-icon">{doc.document_name.toLowerCase().endsWith(".pdf") ? "PDF" : "TXT"}</span>
              <span className="doc-name">{doc.document_name}<small>{doc.chunk_count} {doc.chunk_count === 1 ? "section" : "sections"}</small></span>
            </button>
            <button className="delete" title={`Delete ${doc.document_name}`} aria-label={`Delete ${doc.document_name}`} onClick={() => removeDocument(doc.document_name)}>×</button>
          </div>)}
        </div>
        <div className="sidebar-foot">
          <div className="storage-icon">◈</div>
          <div><strong>Private by design</strong><span>Powered by ChromaDB</span></div>
          <span className="storage-status" title="Storage connected" />
        </div>
      </aside>
      <section className="chat-panel">
        <div className="chat-heading">
          <div className="chat-heading-copy">
            <div className="eyebrow"><span className="heading-spark">✳</span> AI-POWERED RESEARCH</div>
            <h2>Ask your knowledge base</h2>
            <p>{selectedDocument ? <>Focused on <strong className="filter-chip">{selectedDocument}</strong></> : "Answers grounded in your documents, with sources you can verify."}</p>
          </div>
          {selectedDocument && <button className="text-button" onClick={() => setSelectedDocument("")}>Clear filter <span>×</span></button>}
        </div>
        {notice && <div className="notice" role="status">{notice}</div>}
        <div className="conversation">
          {messages.length === 0 && <div className="welcome">
            <div className="welcome-visual" aria-hidden="true">
              <div className="visual-orbit orbit-one" /><div className="visual-orbit orbit-two" />
              <div className="visual-core"><span>✳</span></div>
              <div className="visual-card card-one"><i>✦</i><span /></div>
              <div className="visual-card card-two"><i>⌕</i><span /></div>
            </div>
            <div className="welcome-kicker"><span /> YOUR AI RESEARCH PARTNER</div>
            <h3>Big questions.<br /><span>Grounded answers.</span></h3>
            <p>Explore your knowledge base with natural language. Every answer comes with source passages, so you can see exactly where it came from.</p>
            <div className="suggestion-label">A FEW IDEAS TO GET STARTED</div>
            <div className="suggestions">{[
              ["✳", "Summarize the key points"],
              ["⌕", "What are the main requirements?"],
              ["↗", "What does this document say about risks?"],
            ].map(([icon, suggestion]) => <button key={suggestion} onClick={() => setQuestion(suggestion)}><span className="suggestion-icon">{icon}</span>{suggestion}<span className="suggestion-arrow">↗</span></button>)}</div>
            {documents.length === 0 && <div className="welcome-hint">Start by adding a document to your library <span>↖</span></div>}
          </div>}
          {messages.map((m, i) => <article className={`message ${m.role}`} key={i}>
            <div className="avatar">{m.role === "user" ? "You" : m.role === "assistant" ? "✳" : "!"}</div>
            <div className="message-body"><div className="message-label">{m.role === "user" ? "YOU" : m.role === "assistant" ? "KNOWLEDGE STUDIO" : "ERROR"}</div>
              <p>{m.text}</p>
              {m.sources?.length > 0 && <div className="sources"><div className="sources-title">Retrieved sources</div>
                {m.sources.map((s, j) => <details key={`${s.document_name}-${s.chunk_index}-${j}`}><summary><span className="source-tag">SOURCE {j + 1}</span><span>{s.document_name} · Chunk {s.chunk_index}</span><span className="chevron">⌄</span></summary><blockquote>{s.excerpt}</blockquote></details>)}
              </div>}
              {m.role === "assistant" && m.text !== FALLBACK && <div className="grounding-note">Source passages shown below are the retrieved evidence; verify each claim against them.</div>}
            </div>
          </article>)}
          {asking && <article className="message assistant thinking"><div className="avatar">✳</div><div className="message-body"><div className="message-label">KNOWLEDGE STUDIO</div><p className="typing">Searching your library and preparing a grounded answer<span className="thinking-indicator" aria-label="Generating"><i /><i /><i /></span></p></div></article>}
          <div ref={bottomRef} />
        </div>
        <form className="composer" onSubmit={ask}>
          <div className="composer-prompt"><span className="composer-spark">✳</span><textarea aria-label="Ask a question about your documents" value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(e); } }} placeholder="Ask anything about your documents…" rows={2} /></div>
          <div className="composer-bottom"><span><kbd>↵</kbd> to send <i /> <kbd>⇧ ↵</kbd> for a new line</span><button className="primary send" disabled={asking || !question.trim()} type="submit">{asking ? <><span className="button-spinner" /> Thinking…</> : <>Ask Studio <span>↗</span></>}</button></div>
        </form>
      </section>
    </main>
    <footer><span className="footer-brand">✳ KNOWLEDGE STUDIO</span><span>AI can make mistakes. Verify important answers against the source documents.</span><span className="footer-stack">REACT <i /> FASTAPI <i /> CHROMADB</span></footer>
  </div>;
}
