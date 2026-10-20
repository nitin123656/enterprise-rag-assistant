import { useEffect, useRef, useState } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const FALLBACK = "I am sorry, but the provided documents do not contain enough information to answer this question.";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState("");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [notice, setNotice] = useState("");
  const [messages, setMessages] = useState([]);
  const bottomRef = useRef(null);

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

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand-mark">K</div>
      <div><div className="eyebrow">ENTERPRISE AI</div><h1>Knowledge Assistant</h1></div>
      <div className="status"><span /> RAG pipeline</div>
    </header>
    <main className="layout">
      <aside className="sidebar">
        <div className="section-title">KNOWLEDGE BASE</div>
        <label className="upload-zone">
          <input type="file" accept=".pdf,.txt,application/pdf,text/plain" onChange={e => setFile(e.target.files?.[0] || null)} />
          <span className="upload-icon">↑</span><strong>{file ? file.name : "Add a document"}</strong>
          <small>PDF or TXT · Max 15 MB</small>
        </label>
        <button className="primary full" onClick={upload} disabled={uploading || !file}>{uploading ? "Indexing document…" : "Upload & index"}</button>
        <div className="list-heading"><span>Indexed documents</span><span className="count">{documents.length}</span></div>
        <div className="document-list">
          {documents.length === 0 && <p className="muted small">Your uploaded documents will appear here.</p>}
          {documents.map(doc => <div className={`doc-row ${selectedDocument === doc.document_name ? "selected" : ""}`} key={doc.document_name}>
            <button className="doc-select" onClick={() => setSelectedDocument(selectedDocument === doc.document_name ? "" : doc.document_name)} title="Filter questions to this document">
              <span className="file-icon">▤</span><span className="doc-name">{doc.document_name}<small>{doc.chunk_count} chunks</small></span>
            </button>
            <button className="delete" title={`Delete ${doc.document_name}`} onClick={() => removeDocument(doc.document_name)}>×</button>
          </div>)}
        </div>
        <div className="sidebar-foot">Local vector storage<br /><span>ChromaDB · cosine distance</span></div>
      </aside>
      <section className="chat-panel">
        <div className="chat-heading"><div><div className="eyebrow">DOCUMENT SEARCH</div><h2>Ask your knowledge base</h2><p>{selectedDocument ? <>Searching <strong>{selectedDocument}</strong></> : "Answers are grounded in your indexed documents."}</p></div>
          {selectedDocument && <button className="text-button" onClick={() => setSelectedDocument("")}>Search all</button>}
        </div>
        {notice && <div className="notice" role="status">{notice}</div>}
        <div className="conversation">
          {messages.length === 0 && <div className="welcome">
            <div className="welcome-symbol">✳</div><h3>What would you like to know?</h3>
            <p>Upload a document, then ask a question. Answers include retrieved source passages so you can verify the evidence.</p>
            <div className="suggestions">{["Summarize the key points", "What are the main requirements?", "What does this document say about risks?"].map(s => <button key={s} onClick={() => setQuestion(s)}>{s}<span>↗</span></button>)}</div>
          </div>}
          {messages.map((m, i) => <article className={`message ${m.role}`} key={i}>
            <div className="avatar">{m.role === "user" ? "You" : m.role === "assistant" ? "AI" : "!"}</div>
            <div className="message-body"><div className="message-label">{m.role === "user" ? "YOU" : m.role === "assistant" ? "KNOWLEDGE ASSISTANT" : "ERROR"}</div>
              <p>{m.text}</p>
              {m.sources?.length > 0 && <div className="sources"><div className="sources-title">Retrieved sources</div>
                {m.sources.map((s, j) => <details key={`${s.document_name}-${s.chunk_index}-${j}`}><summary><span className="source-tag">SOURCE {j + 1}</span><span>{s.document_name} · Chunk {s.chunk_index}</span><span className="chevron">⌄</span></summary><blockquote>{s.excerpt}</blockquote></details>)}
              </div>}
              {m.role === "assistant" && m.text !== FALLBACK && <div className="grounding-note">Source passages shown below are the retrieved evidence; verify each claim against them.</div>}
            </div>
          </article>)}
          {asking && <article className="message assistant"><div className="avatar">AI</div><div className="message-body"><div className="message-label">KNOWLEDGE ASSISTANT</div><p className="typing">Searching document chunks and generating a grounded answer…</p></div></article>}
          <div ref={bottomRef} />
        </div>
        <form className="composer" onSubmit={ask}>
          <textarea value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(e); } }} placeholder="Ask a question about your documents…" rows={2} />
          <div className="composer-bottom"><span>Enter to send · Shift + Enter for a new line</span><button className="primary send" disabled={asking || !question.trim()} type="submit">{asking ? "Working…" : "Ask assistant ↗"}</button></div>
        </form>
      </section>
    </main>
    <footer>Built with React · FastAPI · ChromaDB · Gemini <span>Answers may be incomplete; verify important information against source documents.</span></footer>
  </div>;
}
