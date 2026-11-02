import { useEffect, useState } from 'react';
import { request } from '../services/api';
import './utility-ledger.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);

export default function TenantUtilities({ shares, onRefresh }) {
  const [busyShare, setBusyShare] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const interval = setInterval(onRefresh, 10000);
    window.addEventListener('focus', onRefresh);
    return () => { clearInterval(interval); window.removeEventListener('focus', onRefresh); };
  }, []);

  async function markPaid(share) {
    setBusyShare(share.share_id); setMessage(''); setError('');
    try {
      await request(`/utilities/${share.share_id}/mark-paid`, { method: 'PATCH' });
      await onRefresh();
      setMessage('Payment submitted for admin verification.');
    } catch (caught) { setError(caught.message); } finally { setBusyShare(null); }
  }

  const remaining = shares.filter(share => share.payment_status !== 'Paid')
    .reduce((total, share) => total + Number(share.owed_amt), 0);

  return <section className="tenant-utilities">
    <div className="page-title"><div><p className="eyebrow">SHARED LIVING</p><h1>My utility bills</h1><p className="muted">See your share, submit a payment for verification, and follow every status change. Updates appear automatically within 10 seconds.</p></div><button className="soft-button" onClick={onRefresh}>Refresh</button></div>
    <div className="utility-tenant-balance panel"><span>Amount awaiting verified payment</span><strong>{money(remaining)}</strong></div>
    {message && <p className="success-text" role="status">{message}</p>}
    {error && <p className="error banner" role="alert">{error}</p>}
    <div className="tenant-utility-list">{shares.map(share => <article className="panel tenant-utility-card" key={share.share_id}>
      <div className="utility-bill-head"><div><p className="eyebrow">BILL #{share.bill_id}</p><h2>{share.unit_label ?? `Unit #${share.unit_id}`}</h2><p className="muted">Billed {share.bill_date} · Due {share.due_date}</p></div><strong>{money(share.owed_amt)}</strong></div>
      <div className="tenant-utility-foot"><span className={`badge ${share.payment_status === 'Paid' ? 'paid' : share.payment_status === 'Pending Verification' ? 'pending-verification' : 'unpaid'}`}>{share.payment_status}</span><span className="muted">Total bill {money(share.total_amount)}</span>{share.payment_status === 'Unpaid' && <button className="primary compact" disabled={busyShare === share.share_id} onClick={() => markPaid(share)}>{busyShare === share.share_id ? 'Submitting...' : 'I paid this share'}</button>}</div>
      <details className="utility-history"><summary>Payment history ({share.ledger?.length ?? 0})</summary><ol>{(share.ledger ?? []).map(entry => <li key={entry.log_id}><strong>{entry.new_status}</strong> · {entry.recorded_by}<small>{entry.note} · {new Date(entry.created_at).toLocaleString()}</small></li>)}</ol></details>
    </article>)}{!shares.length && <article className="panel"><p className="muted">No utility bills have been assigned to your account yet.</p></article>}</div>
  </section>;
}
