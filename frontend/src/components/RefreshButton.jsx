import { useState } from 'react';
import './refresh-button.css';

export default function RefreshButton({ onRefresh, children = 'Refresh', className = 'soft-button' }) {
  const [state, setState] = useState('idle');
  const [updatedAt, setUpdatedAt] = useState('');

  async function refresh() {
    if (state === 'loading') return;
    setState('loading');
    try {
      const succeeded = await onRefresh();
      if (succeeded === false) {
        setState('failed');
      } else {
        setUpdatedAt(new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        setState('done');
      }
    } catch {
      setState('failed');
    }
  }

  return <span className="refresh-control">
    <button type="button" className={className} onClick={refresh} disabled={state === 'loading'}>
      {state === 'loading' ? 'Refreshing…' : children}
    </button>
    <small className={state === 'failed' ? 'refresh-status refresh-status-error' : 'refresh-status'} role="status" aria-live="polite">
      {state === 'done' ? `Updated ${updatedAt}` : state === 'failed' ? 'Refresh failed' : ''}
    </small>
  </span>;
}
