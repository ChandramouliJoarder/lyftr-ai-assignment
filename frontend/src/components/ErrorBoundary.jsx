import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Uncaught error in Chat UI:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
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
