import React, { useState, useEffect, useRef } from 'react';
import { ChatInput } from './components/ChatInput';
import { AssistantMessage } from './components/AssistantMessage';
import { UserMessage } from './components/UserMessage';
import { NoticeBubble } from './components/NoticeBubble';
import { SystemPromptDrawer } from './components/SystemPromptDrawer';
import { DemoDrawer } from './components/DemoDrawer';
import { ErrorBoundary } from './components/ErrorBoundary';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function generateSessionId() {
  try {
    return `s-${crypto.randomUUID().slice(0, 8)}`;
  } catch {
    return `s-${Math.random().toString(36).substring(2, 10)}`;
  }
}

export default function App() {
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [simulationHeader, setSimulationHeader] = useState('');
  const [theme, setTheme] = useState('light');

  const messagesEndRef = useRef(null);

  // Initialize theme based on preference or toggle
  useEffect(() => {
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = prefersDark ? 'dark' : 'light';
    setTheme(initialTheme);
    document.documentElement.setAttribute('data-theme', initialTheme);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(nextTheme);
    document.documentElement.setAttribute('data-theme', nextTheme);
  };

  // Auto-scroll to bottom of conversation
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleNewChat = () => {
    const newId = generateSessionId();
    setSessionId(newId);
    setMessages([]);
    setInputMessage('');
  };

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend !== undefined ? textToSend : inputMessage).trim();
    if (!text || isLoading) return;

    if (text.length > 4000) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'notice',
          content: 'Please type a message (up to 4000 characters).',
          isError: true,
        },
      ]);
      return;
    }

    // Add user message
    const userMsgId = `user-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: text,
      },
    ]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const headers = {
        'Content-Type': 'application/json',
      };
      if (simulationHeader) {
        headers['X-Simulate-Failure'] = simulationHeader;
      }

      const payload = {
        session_id: sessionId,
        message: text,
      };
      if (systemPrompt.trim()) {
        payload.system_prompt = systemPrompt.trim();
      }

      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let errorNotice = 'An unexpected error occurred. Please try again.';
        if (response.status === 422) {
          errorNotice = 'Please type a message (up to 4000 characters).';
        } else if (response.status === 503) {
          errorNotice = 'Every AI provider is unavailable right now, try again in a moment.';
        } else {
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errorNotice = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
            }
          } catch {
            // Keep default message
          }
        }

        setMessages((prev) => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'notice',
            content: errorNotice,
            isError: true,
          },
        ]);
        return;
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          id: `asst-${Date.now()}`,
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'notice',
          content: 'Unable to connect to the backend server. Please verify the server is running.',
          isError: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const samplePrompts = [
    'What is the capital of France?',
    'Explain the Byzantine Generals Problem in simple terms.',
    'Draft a concise letter of introduction for an engineering guild.',
  ];

  return (
    <ErrorBoundary>
      <div style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-paper)',
      }}>
        {/* Left Side Rail / Desk Drawer */}
        <aside style={{
          width: '290px',
          borderRight: '1px solid var(--border-color)',
          backgroundColor: 'var(--bg-card)',
          padding: '1.75rem 1.25rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }} className="sidebar">
          <div>
            <div style={{ marginBottom: '2rem' }}>
              <span style={{
                fontSize: '0.7rem',
                fontFamily: 'var(--font-mono)',
                color: 'var(--terracotta)',
                textTransform: 'uppercase',
                letterSpacing: '0.12em',
                fontWeight: 600,
              }}>
                Fault-Tolerant LLM Gateway
              </span>
              <h1 style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.5rem',
                fontWeight: 600,
                color: 'var(--ink-primary)',
                marginTop: '0.2rem',
                lineHeight: 1.2,
              }}>
                Correspondence Desk
              </h1>
              <p style={{
                fontSize: '0.8rem',
                color: 'var(--ink-secondary)',
                marginTop: '0.4rem',
              }}>
                Automatic key failover &amp; LiteLLM disk response caching.
              </p>
            </div>

            <button
              onClick={handleNewChat}
              style={{
                width: '100%',
                padding: '0.65rem 1rem',
                backgroundColor: 'transparent',
                border: '1px solid var(--ink-primary)',
                borderRadius: '4px',
                color: 'var(--ink-primary)',
                fontFamily: 'var(--font-sans)',
                fontSize: '0.88rem',
                fontWeight: 500,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                marginBottom: '1.5rem',
                transition: 'all 0.15s ease',
              }}
            >
              <span>+</span>
              <span>New Conversation</span>
            </button>

            {/* Session ID display */}
            <div style={{
              padding: '0.6rem 0.8rem',
              backgroundColor: 'var(--bg-subtle)',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)',
              marginBottom: '1.5rem',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: 'var(--ink-secondary)',
            }}>
              <span style={{ color: 'var(--ink-muted)' }}>Session: </span>
              <span style={{ fontWeight: 600, color: 'var(--ink-primary)' }}>{sessionId}</span>
            </div>

            {/* System Prompt Customization */}
            <SystemPromptDrawer
              value={systemPrompt}
              onChange={setSystemPrompt}
              disabled={isLoading}
            />

            {/* Failover Test Hook */}
            <DemoDrawer
              simulationHeader={simulationHeader}
              onSelectSimulation={setSimulationHeader}
            />
          </div>

          {/* Sidebar Footer */}
          <div style={{
            paddingTop: '1rem',
            borderTop: '1px solid var(--border-color)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.78rem',
            color: 'var(--ink-muted)',
            fontFamily: 'var(--font-mono)',
          }}>
            <span>LiteLLM + SQLite</span>
            <button
              onClick={toggleTheme}
              style={{
                background: 'none',
                border: '1px solid var(--border-color)',
                borderRadius: '3px',
                padding: '2px 8px',
                cursor: 'pointer',
                color: 'var(--ink-secondary)',
                fontSize: '0.75rem',
              }}
            >
              {theme === 'light' ? '☾ Dark' : '☼ Light'}
            </button>
          </div>
        </aside>

        {/* Main Conversation Column */}
        <main style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          overflow: 'hidden',
        }}>
          {/* Messages Scroll Area */}
          <div
            aria-live="polite"
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '2rem 3rem',
              maxWidth: '860px',
              width: '100%',
              margin: '0 auto',
            }}
          >
            {messages.length === 0 ? (
              <div style={{
                textAlign: 'center',
                padding: '4rem 1rem 2rem',
              }}>
                <div style={{
                  display: 'inline-block',
                  width: '42px',
                  height: '42px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--terracotta-light)',
                  color: 'var(--terracotta)',
                  lineHeight: '42px',
                  fontSize: '1.25rem',
                  marginBottom: '1rem',
                }}>
                  ✦
                </div>
                <h2 style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.65rem',
                  fontWeight: 500,
                  color: 'var(--ink-primary)',
                  marginBottom: '0.5rem',
                }}>
                  A clean sheet for your inquiry
                </h2>
                <p style={{
                  color: 'var(--ink-secondary)',
                  fontSize: '0.92rem',
                  maxWidth: '460px',
                  margin: '0 auto 2rem',
                  lineHeight: 1.5,
                }}>
                  Inquiries are answered via a resilient multi-key pool with automated failover and disk-persisted response caching.
                </p>

                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.65rem',
                  maxWidth: '480px',
                  margin: '0 auto',
                  textAlign: 'left',
                }}>
                  <span style={{
                    fontSize: '0.72rem',
                    fontFamily: 'var(--font-mono)',
                    color: 'var(--ink-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}>
                    Suggested prompts:
                  </span>
                  {samplePrompts.map((prompt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(prompt)}
                      style={{
                        padding: '0.65rem 0.95rem',
                        backgroundColor: 'var(--bg-card)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '6px',
                        color: 'var(--ink-primary)',
                        fontFamily: 'var(--font-serif)',
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                        textAlign: 'left',
                        boxShadow: 'var(--shadow-subtle)',
                        transition: 'border-color 0.15s ease',
                      }}
                    >
                      “{prompt}”
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                {messages.map((msg) => {
                  if (msg.role === 'user') {
                    return <UserMessage key={msg.id} content={msg.content} />;
                  } else if (msg.role === 'assistant') {
                    return (
                      <AssistantMessage
                        key={msg.id}
                        content={msg.content}
                        metadata={msg.metadata}
                      />
                    );
                  } else {
                    return (
                      <NoticeBubble
                        key={msg.id}
                        content={msg.content}
                        isError={msg.isError}
                      />
                    );
                  }
                })}

                {isLoading && (
                  <div style={{
                    margin: '1.25rem 0',
                    padding: '1rem 1.25rem',
                    backgroundColor: 'var(--bg-card)',
                    borderLeft: '3px solid var(--terracotta)',
                    borderRadius: '0 6px 6px 0',
                    fontFamily: 'var(--font-serif)',
                    fontStyle: 'italic',
                    color: 'var(--ink-muted)',
                    fontSize: '0.95rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                  }}>
                    <span>Consulting key pool &amp; cache...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Chat Input Floating Footer */}
          <div style={{
            borderTop: '1px solid var(--border-color)',
            backgroundColor: 'var(--bg-paper)',
            padding: '1.25rem 3rem 1.5rem',
            maxWidth: '860px',
            width: '100%',
            margin: '0 auto',
          }}>
            <ChatInput
              value={inputMessage}
              onChange={setInputMessage}
              onSend={() => handleSendMessage()}
              disabled={isLoading}
            />
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
