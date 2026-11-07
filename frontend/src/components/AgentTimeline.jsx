import React, { useState } from 'react';
import {
  Compass,
  Search,
  Scale,
  FileCheck2,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Sparkles,
  AlertCircle,
  HelpCircle,
  Repeat
} from 'lucide-react';

export default function AgentTimeline({ steps = [], isRunning = false, activeNode = null }) {
  const [expandedStep, setExpandedStep] = useState(null);

  const toggleExpand = (index) => {
    setExpandedStep(expandedStep === index ? null : index);
  };

  if (!steps || steps.length === 0) {
    return (
      <div className="timeline-empty-state">
        <div className="empty-state-icon">
          <Compass size={32} className="text-slate-500" />
        </div>
        <p className="empty-state-title">Agent Execution Trace</p>
        <p className="empty-state-desc">
          Enter a topic and start research. The LangGraph agent will display its multi-step planning,
          web searches, gap reflection loops, and source synthesis in real-time here.
        </p>
      </div>
    );
  }

  const getNodeIcon = (node, status) => {
    if (status === 'running') {
      return <Loader2 size={18} className="animate-spin text-cyan-400" />;
    }
    switch (node) {
      case 'planner':
        return <Compass size={18} className="text-indigo-400" />;
      case 'searcher':
        return <Search size={18} className="text-emerald-400" />;
      case 'critic':
        return <Scale size={18} className="text-amber-400" />;
      case 'synthesizer':
      case 'report':
        return <Sparkles size={18} className="text-fuchsia-400" />;
      default:
        return <CheckCircle2 size={18} className="text-cyan-400" />;
    }
  };

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <div className="flex items-center gap-2">
          <h3 className="timeline-title">Agent Execution Trace</h3>
          {isRunning && (
            <span className="badge-running">
              <span className="pulse-dot"></span>
              Active Agent Loop
            </span>
          )}
        </div>
        <span className="timeline-count">{steps.length} Steps Logged</span>
      </div>

      <div className="timeline-list">
        {steps.map((step, idx) => {
          const isCurrentRunning = isRunning && idx === steps.length - 1 && step.status === 'running';
          const isExpanded = expandedStep === idx || isCurrentRunning;

          return (
            <div
              key={idx}
              className={`timeline-item ${isCurrentRunning ? 'timeline-item-active' : ''} ${
                step.status === 'failed' ? 'timeline-item-error' : ''
              }`}
            >
              {/* Connector line */}
              {idx < steps.length - 1 && <div className="timeline-connector"></div>}

              {/* Step Icon Badge */}
              <div className={`timeline-badge timeline-badge-${step.node}`}>
                {getNodeIcon(step.node, step.status)}
              </div>

              {/* Content Card */}
              <div className="timeline-card">
                <div
                  className="timeline-card-header"
                  onClick={() => toggleExpand(idx)}
                >
                  <div className="flex items-center gap-2.5 flex-1 min-w-0">
                    <span className="timeline-node-tag">
                      {step.node?.toUpperCase()}
                    </span>
                    <span className="timeline-card-title truncate">
                      {step.title || step.status_message}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    {step.meta && (
                      <span className="timeline-card-meta">{step.meta}</span>
                    )}
                    <button className="expand-trigger">
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="timeline-card-body">
                    {/* Planner Details */}
                    {step.queries && step.queries.length > 0 && (
                      <div className="detail-section">
                        <div className="detail-label">Generated Search Queries:</div>
                        <ul className="query-tags-list">
                          {step.queries.map((q, qIdx) => (
                            <li key={qIdx} className="query-tag">
                              <Search size={12} className="opacity-60 shrink-0" />
                              <span>{q}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Searcher Sources Details */}
                    {step.sources && step.sources.length > 0 && (
                      <div className="detail-section">
                        <div className="detail-label">
                          Discovered Web Sources ({step.sources.length}):
                        </div>
                        <div className="sources-mini-list">
                          {step.sources.map((src, sIdx) => {
                            let domain = '';
                            try {
                              domain = new URL(src.url).hostname.replace('www.', '');
                            } catch (_) {
                              domain = src.url;
                            }
                            return (
                              <a
                                key={sIdx}
                                href={src.url}
                                target="_blank"
                                rel="noreferrer"
                                className="source-mini-chip"
                                title={src.snippet}
                              >
                                <span className="source-domain">{domain}</span>
                                <span className="source-title truncate">{src.title}</span>
                                <ExternalLink size={12} className="opacity-50 shrink-0" />
                              </a>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Critic Details */}
                    {step.node === 'critic' && (
                      <div className="detail-section">
                        <div className="flex items-center gap-2 mb-2">
                          <span
                            className={`badge-status ${
                              step.gaps_found ? 'badge-warning' : 'badge-success'
                            }`}
                          >
                            {step.gaps_found ? (
                              <>
                                <Repeat size={12} /> Gaps Found (Refining)
                              </>
                            ) : (
                              <>
                                <CheckCircle2 size={12} /> Research Sufficient
                              </>
                            )}
                          </span>
                        </div>
                        {step.critique && (
                          <div className="critic-reasoning-box">
                            <span className="font-semibold text-xs block text-slate-400 mb-1">
                              Agent Reflection:
                            </span>
                            <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">
                              {step.critique}
                            </p>
                          </div>
                        )}
                        {step.refined_queries && step.refined_queries.length > 0 && (
                          <div className="mt-2.5">
                            <div className="detail-label">Targeted Follow-up Queries:</div>
                            <ul className="query-tags-list">
                              {step.refined_queries.map((rq, rqIdx) => (
                                <li key={rqIdx} className="query-tag query-tag-refined">
                                  <Search size={12} className="opacity-60 shrink-0" />
                                  <span>{rq}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Report Status */}
                    {step.node === 'synthesizer' && (
                      <div className="detail-section">
                        <p className="text-sm text-emerald-300 flex items-center gap-2">
                          <CheckCircle2 size={16} />
                          Synthesis complete. Executive research dossier rendered.
                        </p>
                      </div>
                    )}

                    {/* Error display */}
                    {step.error && (
                      <div className="error-box">
                        <AlertCircle size={16} className="shrink-0" />
                        <span>{step.error}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
