import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  FileText,
  Copy,
  Check,
  Download,
  Layers,
  Sparkles,
  Clock,
  MessageSquare,
  Send,
  Loader2,
  Bot,
  User,
} from 'lucide-react';
import MermaidBlock from './MermaidBlock';
import { followUpChat } from '../services/api';

export default function ReportViewer({ report = '', topic = '', sources = [], isGenerating = false }) {
  const [copied, setCopied] = useState(false);

  // Follow-up chat state
  const [chatMessages, setChatMessages] = useState([]); // [{role:'user'|'assistant', content:string}]
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  // ── Metrics ──────────────────────────────────────────────────────────────
  const wordCount = report ? report.trim().split(/\s+/).length : 0;
  const readingTimeMin = Math.max(1, Math.ceil(wordCount / 225));

  // ── Clipboard ─────────────────────────────────────────────────────────────
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

  // ── Markdown export ───────────────────────────────────────────────────────
  const handleDownload = () => {
    const filename = `${topic ? topic.slice(0, 30).toLowerCase().replace(/[^a-z0-9]/g, '_') : 'research'}_report.md`;
    const blob = new Blob([report], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // ── Follow-up chat ────────────────────────────────────────────────────────
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    const question = chatInput.trim();
    if (!question || isChatLoading) return;

    setChatInput('');
    setChatError('');
    setChatMessages((prev) => [...prev, { role: 'user', content: question }]);
    setIsChatLoading(true);

    try {
      const { answer } = await followUpChat({ question, dossier: report, topic });
      setChatMessages((prev) => [...prev, { role: 'assistant', content: answer }]);
    } catch (err) {
      setChatError(err.message || 'Failed to get answer.');
    } finally {
      setIsChatLoading(false);
    }
  };

  // ── Custom Markdown components ────────────────────────────────────────────
  const markdownComponents = {
    // Open links in new tab
    a: ({ node, ...props }) => (
      <a {...props} target="_blank" rel="noopener noreferrer" className="dossier-link" />
    ),
    // Responsive table wrapper
    table: ({ node, ...props }) => (
      <div className="table-wrapper">
        <table {...props} className="styled-table" />
      </div>
    ),
    // Intercept ```mermaid code blocks and render as diagrams
    code: ({ node, inline, className, children, ...props }) => {
      const isMermaid = !inline && (className === 'language-mermaid' || String(children).trim().startsWith('graph ') || String(children).trim().startsWith('flowchart ') || String(children).trim().startsWith('sequenceDiagram') || String(children).trim().startsWith('stateDiagram'));
      if (!inline && className === 'language-mermaid') {
        return <MermaidBlock code={String(children).replace(/\n$/, '')} />;
      }
      return inline
        ? <code className={className} {...props}>{children}</code>
        : (
          <pre className="dossier-codeblock">
            <code className={className} {...props}>{children}</code>
          </pre>
        );
    },
  };

  // ── Empty / generating state ──────────────────────────────────────────────
  if (!report) {
    return (
      <div className="report-generating-card">
        <div className="generating-inner">
          <div className="generating-pulse-halo">
            <Sparkles size={24} className="text-amber-400 animate-pulse" />
          </div>
          <h3 className="generating-title">Investigating & Gathering Evidence</h3>
          <p className="generating-desc">
            The LangGraph agent is executing live multi-angle web searches, critiquing knowledge
            sufficiency, and drafting your intelligence report.
          </p>
        </div>
      </div>
    );
  }

  // ── Full report view ──────────────────────────────────────────────────────
  return (
    <div className="report-article-wrapper">

      {/* Header Toolbar */}
      <div className="dossier-header-bar">
        <div className="dossier-meta">
          <span className="dossier-tag">Intelligence Dossier</span>
          <div className="dossier-stats-row">
            <span className="flex items-center gap-1">
              <FileText size={12} /> {wordCount} words
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Clock size={12} /> {readingTimeMin} min read
            </span>
            {sources.length > 0 && (
              <>
                <span>•</span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <Layers size={12} /> {sources.length} citations
                </span>
              </>
            )}
          </div>
        </div>

        <div className="dossier-actions-group">
          <button onClick={handleCopy} className="btn-dossier-action" title="Copy Markdown">
            {copied ? (
              <><Check size={14} className="text-emerald-400" /><span>Copied</span></>
            ) : (
              <><Copy size={14} /><span>Copy</span></>
            )}
          </button>
          <button onClick={handleDownload} className="btn-dossier-action" title="Export Markdown">
            <Download size={14} /><span>Export .md</span>
          </button>
        </div>
      </div>

      {/* Main Markdown Article */}
      <article className="dossier-prose-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
          {report}
        </ReactMarkdown>
      </article>

      {/* Verified Sources / Bibliography */}
      {sources && sources.length > 0 && (
        <section className="dossier-sources-section">
          <div className="sources-header-row">
            <h4 className="sources-heading">Verified Sources & Evidence</h4>
            <span className="sources-badge">{sources.length} Live Citations</span>
          </div>
          <div className="sources-grid-modern">
            {sources.map((src, idx) => {
              let domain = '';
              try { domain = new URL(src.url).hostname.replace('www.', ''); } catch (_) { domain = src.url; }
              return (
                <a
                  key={idx}
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className="source-card-modern"
                >
                  <div className="source-card-head">
                    <span className="source-number">[{idx + 1}]</span>
                    <span className="source-domain-pill">{domain}</span>
                  </div>
                  <span className="source-card-heading line-clamp-2">{src.title}</span>
                  {src.snippet && (
                    <span className="source-card-text line-clamp-2">{src.snippet}</span>
                  )}
                </a>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Follow-up Chat Panel ─────────────────────────────────────────── */}
      <section className="followup-chat-section">
        <div className="followup-chat-header">
          <MessageSquare size={16} style={{ color: 'var(--accent-primary)' }} />
          <span className="followup-chat-title">Ask a follow-up question</span>
          <span className="followup-chat-hint">No new web search — answers from dossier context & AI knowledge</span>
        </div>

        {/* Chat thread */}
        {chatMessages.length > 0 && (
          <div className="chat-thread">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
                <div className="chat-bubble-icon">
                  {msg.role === 'user'
                    ? <User size={13} />
                    : <Bot size={13} style={{ color: 'var(--accent-primary)' }} />}
                </div>
                <div className="chat-bubble-body">
                  {msg.role === 'assistant'
                    ? (
                      <div className="chat-answer-prose">
                        <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    )
                    : <span className="chat-question-text">{msg.content}</span>
                  }
                </div>
              </div>
            ))}
            {isChatLoading && (
              <div className="chat-bubble chat-bubble-assistant">
                <div className="chat-bubble-icon">
                  <Bot size={13} style={{ color: 'var(--accent-primary)' }} />
                </div>
                <div className="chat-bubble-body chat-thinking">
                  <Loader2 size={14} className="animate-spin" />
                  <span>Thinking…</span>
                </div>
              </div>
            )}
          </div>
        )}

        {chatError && (
          <div className="chat-error-row">⚠ {chatError}</div>
        )}

        {/* Input */}
        <form onSubmit={handleChatSubmit} className="followup-chat-form">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="e.g. Can you show Python code for Course Schedule II using Kahn's algorithm?"
            className="followup-chat-input"
            disabled={isChatLoading}
          />
          <button
            type="submit"
            disabled={!chatInput.trim() || isChatLoading}
            className="followup-chat-send"
            title="Send"
          >
            {isChatLoading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          </button>
        </form>
      </section>

    </div>
  );
}
