import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';

export const AssistantMessage = ({ content, metadata }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const isCache = metadata?.resolution_source === 'LLM_CACHE';

  return (
    <div
      data-testid="assistant-message"
      style={{
        margin: '1.5rem 0',
        padding: '1.25rem 1.5rem',
        backgroundColor: 'var(--bg-card)',
        borderLeft: '3px solid var(--terracotta)',
        borderTop: '1px solid var(--border-subtle)',
        borderRight: '1px solid var(--border-subtle)',
        borderBottom: '1px solid var(--border-subtle)',
        borderRadius: '0 8px 8px 0',
        boxShadow: 'var(--shadow-subtle)',
        position: 'relative',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <span style={{
          fontFamily: 'var(--font-serif)',
          fontSize: '0.85rem',
          fontStyle: 'italic',
          color: 'var(--ink-muted)',
          letterSpacing: '0.02em',
        }}>
          Assistant dispatch
        </span>
        <button
          onClick={handleCopy}
          aria-label="Copy message text"
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--ink-muted)',
            cursor: 'pointer',
            fontSize: '0.75rem',
            fontFamily: 'var(--font-mono)',
            padding: '2px 6px',
            borderRadius: '3px',
          }}
        >
          {copied ? 'copied ✓' : 'copy'}
        </button>
      </div>

      <div style={{
        fontFamily: 'var(--font-serif)',
        fontSize: '1.03rem',
        lineHeight: 1.7,
        color: 'var(--ink-primary)',
        wordBreak: 'break-word',
      }}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>

      {metadata && (
        <div style={{
          marginTop: '1.25rem',
          paddingTop: '0.85rem',
          borderTop: '1px dashed var(--border-color)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          color: 'var(--ink-secondary)',
        }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.85rem' }}>
            {/* Rubber stamp for resolution source */}
            <span
              data-testid="meta-source"
              style={{
                display: 'inline-block',
                transform: 'rotate(-1.5deg)',
                padding: '2px 7px',
                borderRadius: '3px',
                fontWeight: 600,
                fontSize: '0.72rem',
                letterSpacing: '0.05em',
                backgroundColor: isCache ? 'var(--stamp-cache-bg)' : 'var(--terracotta-light)',
                color: isCache ? 'var(--stamp-cache)' : 'var(--terracotta)',
                border: `1px solid ${isCache ? 'var(--stamp-cache-border)' : 'var(--terracotta-border)'}`,
              }}
            >
              {metadata.resolution_source}
            </span>

            {/* Model identifier */}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--ink-muted)' }}>model:</span>
              <span data-testid="meta-model" style={{ color: 'var(--ink-primary)' }}>
                {metadata.model}
              </span>
            </span>

            {/* Latency */}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--ink-muted)' }}>latency:</span>
              <span data-testid="meta-latency" style={{ color: 'var(--ink-primary)' }}>
                {metadata.latency_ms} ms
              </span>
            </span>

            {/* Input tokens */}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--ink-muted)' }}>in:</span>
              <span data-testid="meta-input-tokens" style={{ color: 'var(--ink-primary)' }}>
                {metadata.input_tokens}
              </span>
            </span>

            {/* Output tokens */}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ color: 'var(--ink-muted)' }}>out:</span>
              <span data-testid="meta-output-tokens" style={{ color: 'var(--ink-primary)' }}>
                {metadata.output_tokens}
              </span>
            </span>

            {/* Key ID and fallbacks */}
            {metadata.key_id && (
              <span data-testid="meta-key" style={{ color: 'var(--ink-muted)' }}>
                key: {metadata.key_id}
              </span>
            )}
            {metadata.fallback_attempts > 0 && (
              <span data-testid="meta-fallbacks" style={{ color: 'var(--terracotta)' }}>
                fallbacks: {metadata.fallback_attempts}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
