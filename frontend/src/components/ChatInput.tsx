import React, { useRef, useEffect } from 'react';

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
  onSend,
  disabled = false,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const charCount = value.trim().length;
  const isNearLimit = charCount > 3500;
  const isOverLimit = charCount > 4000;

  // Auto-resize textarea height based on content
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && charCount > 0 && !isOverLimit) {
        onSend();
      }
    }
  };

  return (
    <div style={{
      position: 'relative',
      backgroundColor: 'var(--bg-card)',
      border: '1px solid var(--border-color)',
      borderRadius: '8px',
      padding: '0.75rem 0.85rem',
      boxShadow: 'var(--shadow-subtle)',
      transition: 'border-color 0.2s ease',
    }}>
      <textarea
        ref={textareaRef}
        data-testid="chat-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask something, anything... (Enter to dispatch, Shift+Enter for newline)"
        rows={2}
        disabled={disabled}
        aria-label="Chat message input"
        style={{
          width: '100%',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          resize: 'none',
          fontSize: '0.98rem',
          lineHeight: 1.5,
          color: 'var(--ink-primary)',
          fontFamily: 'inherit',
        }}
      />

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: '0.5rem',
        paddingTop: '0.4rem',
        borderTop: '1px solid var(--border-subtle)',
      }}>
        <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
          {isNearLimit && (
            <span style={{ color: isOverLimit ? 'var(--terracotta)' : 'var(--ink-secondary)' }}>
              {charCount} / 4000 {isOverLimit && '(exceeds limit)'}
            </span>
          )}
        </div>

        <button
          data-testid="send-button"
          onClick={onSend}
          disabled={disabled || charCount === 0 || isOverLimit}
          aria-label="Send message"
          style={{
            backgroundColor: disabled || charCount === 0 || isOverLimit ? 'var(--border-color)' : 'var(--terracotta)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '4px',
            padding: '0.45rem 1.1rem',
            fontSize: '0.88rem',
            fontFamily: 'var(--font-sans)',
            fontWeight: 500,
            cursor: disabled || charCount === 0 || isOverLimit ? 'not-allowed' : 'pointer',
            transition: 'background-color 0.15s ease',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          {disabled ? 'Dispatching...' : 'Dispatch ↵'}
        </button>
      </div>
    </div>
  );
};
