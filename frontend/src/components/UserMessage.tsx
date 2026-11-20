import React from 'react';

interface UserMessageProps {
  content: string;
}

export const UserMessage: React.FC<UserMessageProps> = ({ content }) => {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'flex-end',
      margin: '1.25rem 0',
    }}>
      <div style={{
        maxWidth: '85%',
        padding: '0.9rem 1.25rem',
        backgroundColor: 'var(--bg-subtle)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px 8px 2px 8px',
        color: 'var(--ink-primary)',
        fontSize: '0.98rem',
        lineHeight: 1.6,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        boxShadow: 'var(--shadow-subtle)',
      }}>
        {content}
      </div>
    </div>
  );
};
