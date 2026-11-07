import React, { useState } from 'react';
import { KeyRound, Check, X, ShieldAlert, Lock } from 'lucide-react';
import { getStoredPasscode, setStoredPasscode } from '../services/api';

export default function PasscodeModal({ isOpen, onClose, onSaved }) {
  const [passcode, setPasscode] = useState(getStoredPasscode());
  const [savedSuccess, setSavedSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSave = (e) => {
    e.preventDefault();
    setStoredPasscode(passcode);
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      onSaved?.(passcode);
      onClose();
    }, 600);
  };

  const handleClear = () => {
    setPasscode('');
    setStoredPasscode('');
    onSaved?.('');
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-icon-badge">
              <KeyRound size={20} className="text-cyan-400" />
            </div>
            <div>
              <h3 className="modal-title">Access Key & Security</h3>
              <p className="modal-subtitle">Authenticate to execute live agent searches</p>
            </div>
          </div>
          <button className="icon-btn-ghost" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSave} className="modal-body">
          <div className="info-banner">
            <Lock size={16} className="text-cyan-400 shrink-0 mt-0.5" />
            <p>
              This app is protected by a shared passcode to prevent unauthorized usage of search tools
              and Gemini API credits. Enter the passcode configured in your backend.
            </p>
          </div>

          <div className="input-field-group">
            <label htmlFor="passcode-input" className="field-label">
              Passcode (X-App-Key)
            </label>
            <input
              id="passcode-input"
              type="password"
              placeholder="e.g. researcher2026"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              className="styled-input"
              autoFocus
            />
          </div>

          <div className="modal-actions">
            {passcode && (
              <button
                type="button"
                onClick={handleClear}
                className="btn-secondary"
              >
                Clear
              </button>
            )}
            <button
              type="submit"
              className={`btn-primary ${savedSuccess ? 'btn-success' : ''}`}
            >
              {savedSuccess ? (
                <>
                  <Check size={16} /> Saved!
                </>
              ) : (
                'Save Key'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
