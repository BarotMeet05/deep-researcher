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
  Share2,
  Calendar
} from 'lucide-react';

export default function ReportViewer({ report = '', topic = '', sources = [], isGenerating = false }) {
  const [copied, setCopied] = useState(false);

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

  if (!report) {
    return (
      <div className="report-generating-card">
        <div className="generating-inner">
          <div className="generating-pulse-halo">
            <Sparkles size={24} className="text-amber-400 animate-pulse" />
          </div>
          <h3 className="generating-title">Investigating & Gathering Evidence</h3>
          <p className="generating-desc">
            The LangGraph agent is executing live multi-angle web searches, critiquing knowledge sufficiency, and drafting your executive intelligence report.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="report-article-wrapper">
      {/* Editorial Report Header Toolbar */}
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
          <button
            onClick={handleCopy}
            className="btn-dossier-action"
            title="Copy Markdown"
          >
            {copied ? (
              <>
                <Check size={14} className="text-emerald-400" />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy size={14} />
                <span>Copy</span>
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            className="btn-dossier-action"
            title="Export Markdown File"
          >
            <Download size={14} />
            <span>Export .md</span>
          </button>
        </div>
      </div>

      {/* Main Markdown Article Content */}
      <article className="dossier-prose-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node, ...props }) => (
              <a
                {...props}
                target="_blank"
                rel="noopener noreferrer"
                className="dossier-link"
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

      {/* Verified Sources / Bibliography Section */}
      {sources && sources.length > 0 && (
        <section className="dossier-sources-section">
          <div className="sources-header-row">
            <h4 className="sources-heading">Verified Sources & Evidence</h4>
            <span className="sources-badge">{sources.length} Live Citations</span>
          </div>
          <div className="sources-grid-modern">
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
                  className="source-card-modern"
                >
                  <div className="source-card-head">
                    <span className="source-number">[{idx + 1}]</span>
                    <span className="source-domain-pill">{domain}</span>
                    <ExternalLink size={12} className="opacity-40 ml-auto" />
                  </div>
                  <h5 className="source-card-heading truncate" title={src.title}>
                    {src.title}
                  </h5>
                  {src.snippet && (
                    <p className="source-card-text line-clamp-2">
                      {src.snippet}
                    </p>
                  )}
                </a>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
