/**
 * MermaidBlock — renders a ```mermaid fenced code block as an SVG diagram.
 * Uses mermaid.js lazy-initialised on first render.
 */
import React, { useEffect, useRef, useState } from 'react';

let mermaidInitialised = false;

async function ensureMermaid() {
  if (mermaidInitialised) return;
  const { default: mermaid } = await import('mermaid');
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    themeVariables: {
      background: '#0b0c0e',
      primaryColor: '#1f232d',
      primaryTextColor: '#f3f4f6',
      primaryBorderColor: 'rgba(255,255,255,0.12)',
      lineColor: '#4b5563',
      secondaryColor: '#181b22',
      tertiaryColor: '#121418',
      edgeLabelBackground: '#181b22',
      nodeTextColor: '#f3f4f6',
      clusterBkg: '#121418',
      titleColor: '#e07a5f',
      activationBorderColor: '#e07a5f',
      signalColor: '#9ca3af',
      signalTextColor: '#f3f4f6',
      fontFamily: 'Plus Jakarta Sans, -apple-system, sans-serif',
    },
    flowchart: { curve: 'basis', htmlLabels: true },
  });
  mermaidInitialised = true;
}

let diagramCount = 0;

export default function MermaidBlock({ code }) {
  const containerRef = useRef(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const idRef = useRef(`mermaid-diagram-${++diagramCount}`);

  useEffect(() => {
    if (!code) return;
    let cancelled = false;

    async function render() {
      try {
        await ensureMermaid();
        const { default: mermaid } = await import('mermaid');
        const { svg: rendered } = await mermaid.render(idRef.current, code.trim());
        if (!cancelled) setSvg(rendered);
      } catch (err) {
        if (!cancelled) {
          console.warn('Mermaid render error:', err);
          setError(String(err?.message || err));
        }
      }
    }

    render();
    return () => { cancelled = true; };
  }, [code]);

  if (error) {
    return (
      <div className="mermaid-error-block">
        <span className="mermaid-error-label">⚠ Diagram parse error</span>
        <pre className="mermaid-error-code">{code}</pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="mermaid-loading">
        <span className="pulse-indicator" style={{ display: 'inline-block', marginRight: 8 }} />
        Rendering diagram…
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="mermaid-block"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
