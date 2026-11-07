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
  Zap,
  Globe,
  SlidersHorizontal
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

  // Modals & Drawers
  const [isPasscodeOpen, setIsPasscodeOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [hasPasscode, setHasPasscode] = useState(Boolean(getStoredPasscode()));
  const [history, setHistory] = useState([]);

  // Stream Abort Controller
  const abortControllerRef = useRef(null);

  // Load history & passcode on mount
  useEffect(() => {
    setHistory(getResearchHistory());
    setHasPasscode(Boolean(getStoredPasscode()));
  }, []);

  const handleStartResearch = async (customTopic = null) => {
    const targetTopic = (customTopic || topic).trim();
    if (!targetTopic) return;

    if (customTopic) {
      setTopic(customTopic);
    }

    // Reset research view
    setError(null);
    setReport('');
    setSources([]);
    setSteps([]);
    setIsRunning(true);
    setActiveNode('planner');

    // Create abort controller for cancelling
    const controller = new AbortController();
    abortControllerRef.current = controller;

    // Track state locally for callback closures
    let collectedSources = [];
    let generatedReport = '';
    let currentSteps = [];

    const updateStep = (node, patch) => {
      setSteps((prev) => {
        const copy = [...prev];
        const existingIdx = copy.findIndex((s) => s.node === node && s.status === 'running');
        if (existingIdx !== -1) {
          copy[existingIdx] = { ...copy[existingIdx], ...patch };
          currentSteps = copy;
          return copy;
        } else {
          const newStep = { node, ...patch };
          currentSteps = [...copy, newStep];
          return currentSteps;
        }
      });
    };

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
              meta: `${data.queries?.length || 0} sub-queries`,
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
              title: 'Web Evidence Retrieval',
              status_message: data.status_message,
              sources: newSources,
              meta: `${newSources.length} sources found`,
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
              title: data.gaps_found ? 'Critic: Knowledge Gaps Detected' : 'Critic: Evidence Verified',
              status_message: data.status_message,
              critique: data.critique,
              gaps_found: data.gaps_found,
              refined_queries: data.refined_queries,
              meta: data.gaps_found ? 'Refining searches...' : 'Passed reflection',
            },
          ]);
        },
        onReport: (data) => {
          setActiveNode('synthesizer');
          generatedReport = data.report || '';
          setReport(generatedReport);

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

          // Save completed research to LocalStorage history
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

  const handleSelectHistoryReport = (item) => {
    setTopic(item.topic || '');
    setReport(item.report || '');
    setSources(item.sources || []);
    setSteps(item.steps || []);
    setError(null);
  };

  const handleDeleteHistoryReport = (id) => {
    const updated = deleteHistoryItem(id);
    setHistory(updated);
  };

  const handleClearAllHistory = () => {
    clearAllHistory();
    setHistory([]);
  };

  return (
    <div className="app-shell">
      {/* Top Header Navigation */}
      <header className="app-header">
        <div className="header-brand">
          <div className="brand-logo-badge">
            <Compass size={22} className="text-cyan-400 animate-spin-slow" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="brand-title">DeepResearcher</h1>
              <span className="brand-tag">LangGraph Agent</span>
            </div>
            <p className="brand-tagline">Autonomous Multi-Step Evidence Retrieval & Dossier Synthesis</p>
          </div>
        </div>

        <div className="header-actions">
          <button
            className={`btn-header-pill ${hasPasscode ? 'pill-authenticated' : 'pill-unauthenticated'}`}
            onClick={() => setIsPasscodeOpen(true)}
            title="Configure Access Passcode"
          >
            {hasPasscode ? (
              <>
                <ShieldCheck size={14} className="text-emerald-400" />
                <span>Passcode Set</span>
              </>
            ) : (
              <>
                <KeyRound size={14} className="text-amber-400" />
                <span>Set Key</span>
              </>
            )}
          </button>

          <button
            className="btn-header-pill"
            onClick={() => setIsHistoryOpen(true)}
            title="View Research History"
          >
            <History size={14} className="text-cyan-400" />
            <span>History</span>
            {history.length > 0 && <span className="pill-badge">{history.length}</span>}
          </button>
        </div>
      </header>

      {/* Main App Workspace */}
      <main className="app-main">
        {/* Research Query Console */}
        <section className="search-console-container">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleStartResearch();
            }}
            className="search-console-form"
          >
            <div className="search-input-wrapper">
              <Search size={20} className="search-input-icon" />
              <input
                type="text"
                placeholder="Ask any complex research question, technology trade-off, market analysis..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                disabled={isRunning}
                className="search-input"
              />

              {isRunning ? (
                <button
                  type="button"
                  onClick={handleStopResearch}
                  className="btn-cancel-research"
                  title="Stop agent run"
                >
                  <StopCircle size={18} />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!topic.trim()}
                  className="btn-execute-research"
                >
                  <span>Research</span>
                  <ArrowRight size={18} />
                </button>
              )}
            </div>

            {/* Depth Controls & Configuration */}
            <div className="search-controls-bar">
              <div className="flex items-center gap-3">
                <span className="control-label flex items-center gap-1.5">
                  <SlidersHorizontal size={13} className="text-cyan-400" />
                  Depth:
                </span>
                <div className="depth-toggle-group">
                  <button
                    type="button"
                    onClick={() => setMaxIterations(1)}
                    className={`depth-toggle-btn ${maxIterations === 1 ? 'depth-active' : ''}`}
                    disabled={isRunning}
                  >
                    <Zap size={13} />
                    <span>Quick Scan (1 Loop)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setMaxIterations(2)}
                    className={`depth-toggle-btn ${maxIterations === 2 ? 'depth-active' : ''}`}
                    disabled={isRunning}
                  >
                    <Sparkles size={13} />
                    <span>Deep Critique (2 Loops)</span>
                  </button>
                </div>
              </div>

              <div className="agent-runtime-badge">
                <span className="runtime-indicator"></span>
                <span>Gemini 2.5 Flash • DuckDuckGo Live Web</span>
              </div>
            </div>
          </form>

          {/* Quick Example Starter Pills */}
          {!steps.length && !report && (
            <div className="examples-container">
              <span className="examples-label">Try an example inquiry:</span>
              <div className="examples-grid">
                {EXAMPLE_TOPICS.map((ex, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleStartResearch(ex)}
                    className="example-chip"
                  >
                    <ChevronRight size={13} className="example-chip-arrow" />
                    <span>{ex}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div className="error-alert-banner">
              <AlertCircle size={18} className="shrink-0 text-rose-400" />
              <div className="flex-1 text-sm">
                <span className="font-semibold text-rose-300">Execution Error: </span>
                <span className="text-rose-200">{error}</span>
              </div>
              {error.includes('Passcode') && (
                <button
                  onClick={() => setIsPasscodeOpen(true)}
                  className="btn-alert-action"
                >
                  Enter Key
                </button>
              )}
            </div>
          )}
        </section>

        {/* Dual Split Work Area (Execution Trace & Dossier Viewer) */}
        <section className="work-grid">
          {/* Left Column: LangGraph Execution Trace */}
          <div className="work-column work-column-timeline">
            <AgentTimeline
              steps={steps}
              isRunning={isRunning}
              activeNode={activeNode}
            />
          </div>

          {/* Right Column: Intelligence Dossier Viewer */}
          <div className="work-column work-column-report">
            <ReportViewer
              report={report}
              topic={topic}
              sources={sources}
              isGenerating={isRunning && activeNode === 'synthesizer'}
            />
          </div>
        </section>
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
