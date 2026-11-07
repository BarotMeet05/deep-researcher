import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  FileText,
  Copy,
  Check,
  Download,
  ExternalLink,
  BookOpen,
  Clock,
  Layers,
  Sparkles,
  Share2
} from 'lucide-react';

export default function ReportViewer({ report = '', topic = '', sources = [], isGenerating = false }) {
  const [copied, setCopied] = useState(false);

  if (!report && !isGenerating) {
    return (
      <div className="report-empty-state">
        <div className="empty-state-icon">
          <BookOpen size={36} className="text-slate-500" />
        </div>
        <h3 className="empty-state-title">No Dossier Generated Yet</h3>
        <p className="empty-state-desc">
          When the LangGraph synthesizer node completes its work, your complete intelligence report,
          comparative tables, key findings, and live verified source citations will appear here.
        </p>
      </div>
    );
  }

  // Calculate metrics
  const wordCount = report ? report.trim().split(/\s+/).length : 0;
  const readingTimeMin = Math.max(1, Math.ceil(wordCount / 225));

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy', err);
    }
  };

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

  return (
    <div className="report-container">
      {/* Report Header Toolbar */}
      <div className="report-toolbar">
        <div className="report-meta-group">
          <div className="flex items-center gap-2">
            <span className="report-badge">Executive Dossier</span>
            {isGenerating && (
              <span className="badge-generating">
                <span className="pulse-dot"></span> Synthesizing Report...
              </span>
            )}
          </div>
          {report && (
            <div className="flex items-center gap-3 text-xs text-slate-400 mt-1">
              <span className="flex items-center gap-1">
                <FileText size={13} /> {wordCount} words
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Clock size={13} /> {readingTimeMin} min read
              </span>
              {sources.length > 0 && (
                <>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Layers size={13} /> {sources.length} sources referenced
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {report && (
          <div className="report-actions">
            <button
              onClick={handleCopy}
              className="btn-toolbar"
              title="Copy Markdown to Clipboard"
            >
              {copied ? (
                <>
                  <Check size={15} className="text-emerald-400" /> Copied
                </>
              ) : (
                <>
                  <Copy size={15} /> Copy
                </>
              )}
            </button>
            <button
              onClick={handleDownload}
              className="btn-toolbar"
              title="Download as Markdown file"
            >
              <Download size={15} /> Export .md
            </button>
          </div>
        )}
      </div>

      {/* Markdown Content Area */}
      <div className="report-content-box">
        {report ? (
          <article className="markdown-prose">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ node, ...props }) => (
                  <a
                    {...props}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="report-link"
                  />
                ),
                table: ({ node, ...props }) => (
                  <div className="table-wrapper">
                    <table {...props} className="styled-table" />
                  </div>
                ),
              }}
            >
              {report}
            </ReactMarkdown>
          </article>
        ) : (
          <div className="generating-placeholder">
            <Sparkles size={28} className="animate-pulse text-indigo-400 mb-3" />
            <p className="text-base font-medium text-slate-200">
              Agent is currently synthesizing sources...
            </p>
            <p className="text-xs text-slate-400 mt-1 max-w-md text-center">
              Compiling insights, resolving trade-offs, organizing comparative tables, and generating verified source citations.
            </p>
          </div>
        )}
      </div>

      {/* Verified Sources / Bibliography Section */}
      {sources && sources.length > 0 && (
        <div className="report-sources-section">
          <div className="sources-header">
            <h4 className="sources-title">Verified Sources & Evidence Citations</h4>
            <span className="sources-count">{sources.length} live citations</span>
          </div>
          <div className="sources-grid">
            {sources.map((src, idx) => {
              let domain = '';
              try {
                domain = new URL(src.url).hostname.replace('www.', '');
              } catch (_) {
                domain = src.url;
              }
              return (
                <a
                  key={idx}
                  href={src.url}
                  target="_blank"
                  rel="noreferrer"
                  className="source-card"
                >
                  <div className="source-card-top">
                    <span className="source-index">[{idx + 1}]</span>
                    <span className="source-domain-tag">{domain}</span>
                    <ExternalLink size={12} className="opacity-40 ml-auto shrink-0" />
                  </div>
                  <div className="source-card-title truncate" title={src.title}>
                    {src.title}
                  </div>
                  {src.snippet && (
                    <p className="source-card-snippet line-clamp-2">
                      {src.snippet}
                    </p>
                  )}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
