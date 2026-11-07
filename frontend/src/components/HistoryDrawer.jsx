import React from 'react';
import {
  History,
  Trash2,
  X,
  FileText,
  Calendar,
  Layers,
  ChevronRight,
  Sparkles
} from 'lucide-react';
import { clearAllHistory } from '../services/api';

export default function HistoryDrawer({
  isOpen,
  onClose,
  history = [],
  onSelectReport,
  onDeleteReport,
  onClearHistory
}) {
  if (!isOpen) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer-panel" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="drawer-header">
          <div className="flex items-center gap-2">
            <div className="drawer-icon-badge">
              <History size={18} className="text-cyan-400" />
            </div>
            <div>
              <h3 className="drawer-title">Research History</h3>
              <p className="drawer-subtitle">
                {history.length} saved intelligence dossier{history.length === 1 ? '' : 's'}
              </p>
            </div>
          </div>
          <button className="icon-btn-ghost" onClick={onClose} aria-label="Close drawer">
            <X size={18} />
          </button>
        </div>

        {/* Drawer List */}
        <div className="drawer-body">
          {history.length === 0 ? (
            <div className="drawer-empty-state">
              <Sparkles size={32} className="text-slate-600 mb-2" />
              <p className="text-sm font-medium text-slate-400">No research history yet</p>
              <p className="text-xs text-slate-500 mt-1 max-w-[200px] text-center">
                Completed research dossiers are automatically saved locally in your browser.
              </p>
            </div>
          ) : (
            <div className="history-items-list">
              {history.map((item) => {
                const dateStr = item.timestamp
                  ? new Date(item.timestamp).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : 'Recent';

                return (
                  <div
                    key={item.id}
                    className="history-item-card"
                    onClick={() => {
                      onSelectReport(item);
                      onClose();
                    }}
                  >
                    <div className="history-item-top">
                      <h4 className="history-item-title line-clamp-2" title={item.topic}>
                        {item.topic}
                      </h4>
                      <button
                        className="delete-item-btn"
                        title="Delete research"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteReport(item.id);
                        }}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>

                    <div className="history-item-footer">
                      <span className="flex items-center gap-1 text-[11px] text-slate-400">
                        <Calendar size={11} /> {dateStr}
                      </span>
                      {item.sources && (
                        <span className="flex items-center gap-1 text-[11px] text-cyan-400/80">
                          <Layers size={11} /> {item.sources.length} sources
                        </span>
                      )}
                      <ChevronRight size={14} className="text-slate-500 ml-auto" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Drawer Footer */}
        {history.length > 0 && (
          <div className="drawer-footer">
            <button
              onClick={() => {
                if (window.confirm('Clear all local research history?')) {
                  onClearHistory();
                }
              }}
              className="btn-danger-text"
            >
              <Trash2 size={14} /> Clear all history
            </button>
          </div>
        )}
      </aside>
    </div>
  );
}
