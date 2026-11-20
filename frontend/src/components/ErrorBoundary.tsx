import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in Chat UI:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          maxWidth: '540px',
          margin: '4rem auto',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '8px',
          textAlign: 'center',
          fontFamily: 'var(--font-sans)',
        }}>
          <h2 style={{ fontFamily: 'var(--font-serif)', marginBottom: '1rem', color: 'var(--terracotta)' }}>
            The desk encountered a hitch
          </h2>
          <p style={{ color: 'var(--ink-secondary)', marginBottom: '1.5rem', fontSize: '0.95rem' }}>
            An unexpected error occurred while rendering the conversation. Your session can be safely restored.
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: '0.6rem 1.4rem',
              backgroundColor: 'var(--terracotta)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 500,
            }}
          >
            Refresh Desk
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
