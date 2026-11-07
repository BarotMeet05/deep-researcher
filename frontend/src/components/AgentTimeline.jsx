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
      <div className="timeline-empty-compact">
        <Loader2 size={16} className="animate-spin text-amber-400" />
        <span>Initializing agent state graph...</span>
      </div>
    );
  }

  const getNodeIcon = (node, status) => {
    if (status === 'running') {
      return <Loader2 size={15} className="animate-spin text-amber-400" />;
    }
    switch (node) {
      case 'planner':
        return <Compass size={15} className="text-amber-400" />;
      case 'searcher':
        return <Search size={15} className="text-emerald-400" />;
      case 'critic':
        return <Scale size={15} className="text-sky-400" />;
      case 'synthesizer':
      case 'report':
        return <Sparkles size={15} className="text-amber-300" />;
      default:
        return <CheckCircle2 size={15} className="text-emerald-400" />;
    }
  };

  return (
    <div className="trace-tray-container">
      <div className="trace-tray-list">
        {steps.map((step, idx) => {
          const isCurrentRunning = isRunning && idx === steps.length - 1 && step.status === 'running';
          const isExpanded = expandedStep === idx || isCurrentRunning;

          return (
            <div
              key={idx}
              className={`trace-item ${isCurrentRunning ? 'trace-item-running' : ''} ${
                step.status === 'failed' ? 'trace-item-error' : ''
              }`}
            >
              {/* Connector line */}
              {idx < steps.length - 1 && <div className="trace-connector"></div>}

              {/* Step Icon Badge */}
              <div className={`trace-badge trace-badge-${step.node}`}>
                {getNodeIcon(step.node, step.status)}
              </div>

              {/* Step Content */}
              <div className="trace-card">
                <div
                  className="trace-card-header"
                  onClick={() => toggleExpand(idx)}
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="trace-node-pill">{step.node?.toUpperCase()}</span>
                    <span className="trace-title truncate">
                      {step.title || step.status_message}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {step.meta && <span className="trace-meta">{step.meta}</span>}
                    <button className="trace-expand-btn">
                      {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="trace-card-body">
                    {/* Planner Details */}
                    {step.queries && step.queries.length > 0 && (
                      <div className="trace-detail-group">
                        <span className="trace-detail-label">Search Queries Formulated:</span>
                        <ul className="trace-query-list">
                          {step.queries.map((q, qIdx) => (
                            <li key={qIdx} className="trace-query-item">
                              <Search size={11} className="opacity-50 shrink-0" />
                              <span>{q}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Searcher Sources Details */}
                    {step.sources && step.sources.length > 0 && (
                      <div className="trace-detail-group">
                        <span className="trace-detail-label">
                          Discovered Evidence Sources ({step.sources.length}):
                        </span>
                        <div className="trace-sources-scroll">
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
                                className="trace-source-chip"
                                title={src.snippet}
                              >
                                <span className="trace-source-domain">{domain}</span>
                                <span className="trace-source-title truncate">{src.title}</span>
                                <ExternalLink size={10} className="opacity-40 shrink-0" />
                              </a>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Critic Details */}
                    {step.node === 'critic' && (
                      <div className="trace-detail-group">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span
                            className={`badge-status ${
                              step.gaps_found ? 'badge-warning' : 'badge-success'
                            }`}
                          >
                            {step.gaps_found ? (
                              <>
                                <Repeat size={11} /> Information Gaps Identified
                              </>
                            ) : (
                              <>
                                <CheckCircle2 size={11} /> Evidence Sufficient
                              </>
                            )}
                          </span>
                        </div>
                        {step.critique && (
                          <div className="trace-critique-box">
                            <span className="text-[11px] font-semibold text-slate-400 block mb-1">
                              Critic Reflection:
                            </span>
                            <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                              {step.critique}
                            </p>
                          </div>
                        )}
                        {step.refined_queries && step.refined_queries.length > 0 && (
                          <div className="mt-2">
                            <span className="trace-detail-label">Targeted Follow-up Queries:</span>
                            <ul className="trace-query-list">
                              {step.refined_queries.map((rq, rqIdx) => (
                                <li key={rqIdx} className="trace-query-item trace-query-refined">
                                  <Search size={11} className="opacity-50 shrink-0" />
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
                      <div className="trace-detail-group">
                        <p className="text-xs text-emerald-400 flex items-center gap-1.5 font-medium">
                          <CheckCircle2 size={13} />
                          Synthesis complete. Executive dossier rendered.
                        </p>
                      </div>
                    )}

                    {/* Error display */}
                    {step.error && (
                      <div className="trace-error-box">
                        <AlertCircle size={13} className="shrink-0" />
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
