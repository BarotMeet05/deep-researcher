import React, { useState, useEffect, useRef } from 'react';
import {
  Compass,
  Search,
  Sparkles,
  Layers,
  History,
  KeyRound,
  RotateCcw,
  StopCircle,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Zap,
  Globe,
  SlidersHorizontal,
  Activity,
  FileText,
  CheckCircle2,
  Clock,
  BookOpen
} from 'lucide-react';
import AgentTimeline from './components/AgentTimeline';
import ReportViewer from './components/ReportViewer';
import HistoryDrawer from './components/HistoryDrawer';
import PasscodeModal from './components/PasscodeModal';
import {
  streamResearch,
  getStoredPasscode,
  getResearchHistory,
  saveResearchToHistory,
  deleteHistoryItem,
  clearAllHistory
} from './services/api';

const EXAMPLE_TOPICS = [
  'Compare PostgreSQL vs SQLite for embedded edge applications in 2026',
  'State of Agentic AI Frameworks 2026: LangGraph vs CrewAI vs AutoGen',
  'Commercial viability and breakthrough timeline of Solid-State EV Batteries',
  'Comparison of Next.js 15 vs Remix 2 for high-throughput enterprise SaaS'
];

export default function App() {
  const [topic, setTopic] = useState('');
  const [maxIterations, setMaxIterations] = useState(2);
  const [isRunning, setIsRunning] = useState(false);
  const [activeNode, setActiveNode] = useState(null);
  const [steps, setSteps] = useState([]);
  const [report, setReport] = useState('');
  const [sources, setSources] = useState([]);
  const [error, setError] = useState(null);

  // Flight-Log Tray (Collapsible Inspector)
  const [isTraceExpanded, setIsTraceExpanded] = useState(false);

  // Modals & Drawers
  const [isPasscodeOpen, setIsPasscodeOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [hasPasscode, setHasPasscode] = useState(Boolean(getStoredPasscode()));
  const [history, setHistory] = useState([]);

  // Stream Abort Controller
  const abortControllerRef = useRef(null);

  useEffect(() => {
    setHistory(getResearchHistory());
    setHasPasscode(Boolean(getStoredPasscode()));
  }, []);

  const hasActiveSession = Boolean(isRunning || report || steps.length > 0);

  const handleStartResearch = async (customTopic = null) => {
    const targetTopic = (customTopic || topic).trim();
    if (!targetTopic) return;

    if (customTopic) {
      setTopic(customTopic);
    }

    setError(null);
    setReport('');
    setSources([]);
    setSteps([]);
    setIsRunning(true);
    setActiveNode('planner');
    setIsTraceExpanded(true); // Auto-expand trace during initial search

    const controller = new AbortController();
    abortControllerRef.current = controller;

    let collectedSources = [];
    let generatedReport = '';
    let currentSteps = [];

    try {
      await streamResearch({
        topic: targetTopic,
        maxIterations,
        signal: controller.signal,
        onStart: (data) => {
          setSteps([
            {
              node: 'init',
              status: 'completed',
              title: 'Research Initialized',
              status_message: data.message || `Target: "${targetTopic}"`,
            },
          ]);
        },
        onPlanner: (data) => {
          setActiveNode('planner');
          setSteps((prev) => [
            ...prev,
            {
              node: 'planner',
              status: 'completed',
              title: 'Strategic Query Planning',
              status_message: data.status_message,
              queries: data.queries || [],
              meta: `${data.queries?.length || 0} queries`,
            },
          ]);
        },
        onSearcher: (data) => {
          setActiveNode('searcher');
          const newSources = data.sources || [];
          collectedSources = newSources;
          setSources(newSources);

          setSteps((prev) => [
            ...prev,
            {
              node: 'searcher',
              status: 'completed',
              title: 'Evidence Retrieval',
              status_message: data.status_message,
              sources: newSources,
              meta: `${newSources.length} sources`,
            },
          ]);
        },
        onCritic: (data) => {
          setActiveNode('critic');
          setSteps((prev) => [
            ...prev,
            {
              node: 'critic',
              status: 'completed',
              title: data.gaps_found ? 'Reflection: Knowledge Gaps Found' : 'Reflection: Evidence Verified',
              status_message: data.status_message,
              critique: data.critique,
              gaps_found: data.gaps_found,
              refined_queries: data.refined_queries,
              meta: data.gaps_found ? 'Refining search...' : 'Verified',
            },
          ]);
        },
        onReport: (data) => {
          setActiveNode('synthesizer');
          generatedReport = data.report || '';
          setReport(generatedReport);
          setIsTraceExpanded(false); // Collapse trace when dossier arrives to focus on reading

          setSteps((prev) => [
            ...prev,
            {
              node: 'synthesizer',
              status: 'completed',
              title: 'Executive Dossier Synthesized',
              status_message: data.status_message,
              meta: 'Complete',
            },
          ]);
        },
        onDone: () => {
          setIsRunning(false);
          setActiveNode(null);

          if (generatedReport) {
            const historyItem = {
              id: Date.now().toString(),
              topic: targetTopic,
              timestamp: new Date().toISOString(),
              report: generatedReport,
              sources: collectedSources,
              steps: currentSteps,
              iterations: maxIterations,
            };
            const updated = saveResearchToHistory(historyItem);
            setHistory(updated);
          }
        },
        onError: (err) => {
          setIsRunning(false);
          setActiveNode(null);

          if (err.statusCode === 401 || err.message?.includes('UNAUTHORIZED')) {
            setError('Access Denied: Passcode is required or invalid.');
            setIsPasscodeOpen(true);
          } else {
            setError(err.message || 'An unexpected error occurred during research.');
          }

          setSteps((prev) => [
            ...prev,
            {
              node: 'error',
              status: 'failed',
              title: 'Execution Interrupted',
              status_message: err.message,
              error: err.message,
            },
          ]);
        },
      });
    } catch (err) {
      setIsRunning(false);
      setActiveNode(null);
      setError(err.message || 'Execution failed');
    }
  };

  const handleStopResearch = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsRunning(false);
      setActiveNode(null);
    }
  };

  const handleResetSearch = () => {
    setTopic('');
    setReport('');
    setSources([]);
    setSteps([]);
    setError(null);
    setIsRunning(false);
  };

  const handleSelectHistoryReport = (item) => {
    setTopic(item.topic || '');
    setReport(item.report || '');
    setSources(item.sources || []);
    setSteps(item.steps || []);
    setError(null);
    setIsTraceExpanded(false);
  };

  const handleDeleteHistoryReport = (id) => {
    const updated = deleteHistoryItem(id);
    setHistory(updated);
  };

  const handleClearAllHistory = () => {
    clearAllHistory();
    setHistory([]);
  };

  // Determine current flight log status message
  const getCurrentStatusText = () => {
    if (isRunning) {
      if (activeNode === 'planner') return 'Deconstructing topic into search plan...';
      if (activeNode === 'searcher') return `Searching web & extracting verified evidence... (${sources.length} sources)`;
      if (activeNode === 'critic') return 'Reflecting on evidence completeness & evaluating gaps...';
      if (activeNode === 'synthesizer') return 'Synthesizing executive intelligence dossier with citations...';
      return 'Agent active...';
    }
    if (report) {
      return `Research Complete • ${sources.length} sources cited • ${steps.length} agent steps logged`;
    }
    return '';
  };

  return (
    <div className="app-shell">
      {/* Top Header Navigation */}
      <header className="app-header">
        <div className="header-brand" onClick={handleResetSearch} style={{ cursor: 'pointer' }}>
          <div className="brand-logo-badge">
            <Compass size={18} className="brand-icon" />
          </div>
          <div>
            <h1 className="brand-title">DeepResearcher</h1>
            <span className="brand-sub">Autonomous Research Agent</span>
          </div>
        </div>

        <div className="header-actions">
          {hasActiveSession && (
            <button
              className="btn-header-ghost"
              onClick={handleResetSearch}
              title="Start New Research"
            >
              <RotateCcw size={14} />
              <span className="hidden-xs">New Inquiry</span>
            </button>
          )}

          <button
            className={`btn-header-pill ${hasPasscode ? 'pill-active' : ''}`}
            onClick={() => setIsPasscodeOpen(true)}
            title="Access Security Key"
          >
            {hasPasscode ? (
              <>
                <ShieldCheck size={14} className="text-emerald-400 shrink-0" />
                <span className="hidden-xs">Key Set</span>
              </>
            ) : (
              <>
                <KeyRound size={14} className="text-amber-400 shrink-0" />
                <span>Enter Key</span>
              </>
            )}
          </button>

          <button
            className="btn-header-pill"
            onClick={() => setIsHistoryOpen(true)}
            title="Research Archive"
          >
            <History size={14} className="shrink-0" />
            <span className="hidden-xs">Archive</span>
            {history.length > 0 && <span className="pill-badge">{history.length}</span>}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="app-main">
        {/* VIEW 1: HERO STATE (Clean Perplexity-Style Prompt Console When Idle) */}
        {!hasActiveSession && (
          <section className="hero-section">
            <div className="hero-intro">
              <span className="hero-pill-badge">
                <Sparkles size={13} />
                Multi-Step Reflective Research
              </span>
              <h2 className="hero-headline">
                Investigate complex topics with <span className="hero-gradient-text">verified evidence</span>.
              </h2>
              <p className="hero-subtitle">
                Plans multi-angle queries, searches live sources, critiques knowledge gaps, and synthesizes executive Markdown dossiers.
              </p>
            </div>

            {/* Elevated Command Card */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleStartResearch();
              }}
              className="command-card"
            >
              <div className="command-input-row">
                <Search size={20} className="command-search-icon" />
                <textarea
                  rows={2}
                  placeholder="What would you like to investigate? (e.g. Compare PostgreSQL vs SQLite for embedded edge applications in 2026...)"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleStartResearch();
                    }
                  }}
                  className="command-textarea"
                  autoFocus
                />
              </div>

              <div className="command-bottom-bar">
                <div className="mode-toggle-group">
                  <button
                    type="button"
                    onClick={() => setMaxIterations(1)}
                    className={`mode-toggle-btn ${maxIterations === 1 ? 'mode-active' : ''}`}
                  >
                    <Zap size={12} />
                    <span>Fast Scan</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMaxIterations(2)}
                    className={`mode-toggle-btn ${maxIterations === 2 ? 'mode-active' : ''}`}
                  >
                    <Sparkles size={12} />
                    <span>Deep Critique</span>
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={!topic.trim()}
                  className="btn-command-submit"
                >
                  <span>Research</span>
                  <ArrowRight size={15} />
                </button>
              </div>
            </form>

            {/* Curated Suggested Topics */}
            <div className="curated-suggestions">
              <span className="curated-label">Suggested Inquiries</span>
              <div className="curated-grid">
                {EXAMPLE_TOPICS.map((ex, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleStartResearch(ex)}
                    className="curated-card"
                  >
                    <span className="curated-card-text">{ex}</span>
                    <ArrowRight size={13} className="curated-card-icon" />
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="error-card">
                <AlertCircle size={16} className="text-rose-400 shrink-0" />
                <span className="text-sm text-rose-200">{error}</span>
              </div>
            )}
          </section>
        )}

        {/* VIEW 2: ACTIVE / RESULTS STATE */}
        {hasActiveSession && (
          <section className="results-section">
            {/* Compact Search Bar in Active State */}
            <div className="active-query-bar">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleStartResearch();
                }}
                className="compact-search-form"
              >
                <Search size={16} className="text-slate-400 shrink-0" />
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  disabled={isRunning}
                  placeholder="Ask a follow-up or new topic..."
                  className="compact-search-input"
                />
                {isRunning ? (
                  <button
                    type="button"
                    onClick={handleStopResearch}
                    className="btn-cancel-compact"
                  >
                    <StopCircle size={15} />
                    <span>Cancel</span>
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!topic.trim()}
                    className="btn-submit-compact"
                  >
                    <ArrowRight size={15} />
                  </button>
                )}
              </form>
            </div>

            {/* Collapsible Agent Activity Bar (Flight-Log) */}
            <div className="flight-log-strip">
              <div
                className="flight-log-summary"
                onClick={() => setIsTraceExpanded(!isTraceExpanded)}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  {isRunning ? (
                    <span className="pulse-indicator"></span>
                  ) : (
                    <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                  )}
                  <span className="flight-log-status truncate">
                    {getCurrentStatusText()}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <span className="flight-log-toggle-text">
                    {isTraceExpanded ? 'Hide Trace' : 'Inspect Trace'}
                  </span>
                  {isTraceExpanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </div>
              </div>

              {/* Expandable Flight-Log Trace Panel */}
              {isTraceExpanded && (
                <div className="flight-log-expanded-panel">
                  <AgentTimeline
                    steps={steps}
                    isRunning={isRunning}
                    activeNode={activeNode}
                  />
                </div>
              )}
            </div>

            {/* Verified Sources Horizontal Carousel (Perplexity-Style) */}
            {sources.length > 0 && (
              <div className="sources-ribbon">
                <span className="sources-ribbon-label">Sources ({sources.length}):</span>
                <div className="sources-ribbon-scroll">
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
                        className="source-ribbon-chip"
                        title={src.title}
                      >
                        <span className="source-ribbon-num">[{idx + 1}]</span>
                        <span className="source-ribbon-domain">{domain}</span>
                        <ExternalLink size={11} className="opacity-40" />
                      </a>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Center-Stage Executive Research Dossier */}
            <div className="dossier-workspace">
              <ReportViewer
                report={report}
                topic={topic}
                sources={sources}
                isGenerating={isRunning && activeNode === 'synthesizer'}
              />
            </div>
          </section>
        )}
      </main>

      {/* Modals & Drawers */}
      <PasscodeModal
        isOpen={isPasscodeOpen}
        onClose={() => setIsPasscodeOpen(false)}
        onSaved={(code) => setHasPasscode(Boolean(code))}
      />

      <HistoryDrawer
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        history={history}
        onSelectReport={handleSelectHistoryReport}
        onDeleteReport={handleDeleteHistoryReport}
        onClearHistory={handleClearAllHistory}
      />
    </div>
  );
}
