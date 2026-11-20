import React, { useState } from 'react';

interface SystemPromptDrawerProps {
  value: string;
  onChange: (val: string) => void;
  disabled?: boolean;
}

export const SystemPromptDrawer: React.FC<SystemPromptDrawerProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{
      marginBottom: '1rem',
      backgroundColor: 'var(--bg-card)',
      border: '1px solid var(--border-color)',
      borderRadius: '6px',
      overflow: 'hidden',
    }}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '100%',
          textAlign: 'left',
          padding: '0.65rem 0.9rem',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontFamily: 'var(--font-sans)',
          fontSize: '0.85rem',
          color: 'var(--ink-secondary)',
          fontWeight: 500,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span>✎</span>
          <span>Instructions for the Assistant (System Prompt)</span>
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
          {isOpen ? '▲ hide' : '▼ customize'}
        </span>
      </button>

      {isOpen && (
        <div style={{
          padding: '0.75rem 0.9rem 0.9rem',
          borderTop: '1px solid var(--border-subtle)',
          backgroundColor: 'var(--bg-subtle)',
        }}>
          <p style={{
            fontSize: '0.78rem',
            color: 'var(--ink-muted)',
            marginBottom: '0.5rem',
            lineHeight: 1.4,
          }}>
            Set a persona or guidelines for this conversation session. Persisted across turns.
          </p>
          <textarea
            data-testid="system-prompt-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            placeholder="e.g. You are an 18th-century archivist cataloging rare manuscripts. Answer with historical precision."
            rows={2}
            style={{
              width: '100%',
              padding: '0.5rem',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '4px',
              fontSize: '0.85rem',
              fontFamily: 'inherit',
              color: 'var(--ink-primary)',
              resize: 'vertical',
            }}
          />
        </div>
      )}
    </div>
  );
};
