import React, { useState } from 'react';

interface DemoDrawerProps {
  simulationHeader: string;
  onSelectSimulation: (val: string) => void;
}

export const DemoDrawer: React.FC<DemoDrawerProps> = ({
  simulationHeader,
  onSelectSimulation,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const options = [
    { label: 'Normal operation (no simulation)', value: '' },
    { label: 'Failover key_1 (429 Rate Limit) → Succeed on key_2', value: 'key_1=429' },
    { label: 'Failover key_1 (500 Server Error) → Succeed on key_2', value: 'key_1=500' },
    { label: 'Wildcard failure (*=429) → Expect 503 unavailable', value: '*=429' },
    { label: 'Exhaust both keys (key_1=429,key_2=500) → Expect 503', value: 'key_1=429,key_2=500' },
  ];

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
          <span>⚙</span>
          <span>Failover Demo Laboratory (X-Simulate-Failure)</span>
          {simulationHeader && (
            <span style={{
              fontSize: '0.7rem',
              fontFamily: 'var(--font-mono)',
              backgroundColor: 'var(--terracotta-light)',
              color: 'var(--terracotta)',
              padding: '1px 6px',
              borderRadius: '3px',
              fontWeight: 600,
            }}>
              ACTIVE: {simulationHeader}
            </span>
          )}
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
          {isOpen ? '▲ hide' : '▼ test hook'}
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
            Attaches the <code>X-Simulate-Failure</code> header to the next request to test automated key failover.
          </p>
          <select
            value={simulationHeader}
            onChange={(e) => onSelectSimulation(e.target.value)}
            style={{
              width: '100%',
              padding: '0.5rem',
              backgroundColor: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              borderRadius: '4px',
              fontSize: '0.85rem',
              color: 'var(--ink-primary)',
              cursor: 'pointer',
            }}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};
