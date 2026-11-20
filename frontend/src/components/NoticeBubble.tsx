import React from 'react';

interface NoticeBubbleProps {
  content: string;
  isError?: boolean;
}

export const NoticeBubble: React.FC<NoticeBubbleProps> = ({ content, isError = true }) => {
  return (
    <div
      role="alert"
      style={{
        margin: '1rem 0',
        padding: '0.85rem 1.15rem',
        backgroundColor: isError ? 'var(--terracotta-light)' : 'var(--bg-subtle)',
        border: `1px solid ${isError ? 'var(--terracotta-border)' : 'var(--border-color)'}`,
        borderRadius: '6px',
        color: isError ? 'var(--terracotta)' : 'var(--ink-secondary)',
        fontSize: '0.9rem',
        lineHeight: 1.5,
        display: 'flex',
        alignItems: 'center',
        gap: '0.65rem',
      }}
    >
      <span style={{ fontSize: '1.1rem' }}>{isError ? '✦' : 'ℹ'}</span>
      <span>{content}</span>
    </div>
  );
};
