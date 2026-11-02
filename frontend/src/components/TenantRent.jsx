import { useCallback, useEffect, useState } from 'react';
import { request } from '../services/api';
import RefreshButton from './RefreshButton';
import './rent-ledger.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);
const monthLabel = value => new Date(`${value.slice(0, 7)}-01T12:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });

export default function TenantRent() {
  const [shares, setShares] = useState([]);
  const [references, setReferences] = useState({});
  const [working, setWorking] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setShares(await request('/rent/me')); setError(''); return true; }
    catch (caught) { setError(caught.message); return false; }
  }, []);
  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    window.addEventListener('focus', load);
    return () => { clearInterval(interval); window.removeEventListener('focus', load); };
  }, [load]);

  async function report(share) {
    setWorking(share.share_id); setMessage(''); setError('');
    try {
      await request(`/rent/shares/${share.share_id}/report-payment`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reference: references[share.share_id] ?? '' }),
      });
      setReferences(current => ({ ...current, [share.share_id]: '' }));
      setMessage('Payment reported. An admin can now verify it.');
      await load();
    } catch (caught) { setError(caught.message); }
    finally { setWorking(null); }
  }

  return <section className="rent-page"><div className="page-title"><div><p className="eyebrow">MONTHLY RENT</p><h1>My rent shares</h1><p className="muted">Your share and payment history for each billed month. Payments happen outside ApartmentHub.</p></div><RefreshButton onRefresh={load} /></div>
    {message && <p className="success-text" role="status">{message}</p>}
    {error && <p className="error banner" role="alert">{error}</p>}
    <div className="rent-card-grid">{shares.map(share => <article className="panel rent-card" key={share.share_id}>
      <div className="rent-card-head"><div><p className="eyebrow">{monthLabel(share.billing_month)} · LEASE #{share.lease_id}</p><h2>{share.unit_label}</h2></div><span className={`badge ${share.payment_status === 'Paid' ? 'paid' : share.payment_status === 'Pending Verification' ? 'pending-verification' : 'unpaid'}`}>{share.payment_status}</span></div>
      <div className="rent-amount"><span>Your share<strong>{money(share.owed_amt)}</strong></span><span>Full lease rent<strong>{money(share.full_rent)}</strong></span></div>
      {share.payment_status === 'Unpaid' && <div className="rent-report"><label>Payment reference (optional)<input maxLength="100" value={references[share.share_id] ?? ''} onChange={event => setReferences(current => ({ ...current, [share.share_id]: event.target.value }))} placeholder="UPI or bank reference" /></label><button className="primary compact" disabled={working === share.share_id} onClick={() => report(share)}>{working === share.share_id ? 'Reporting...' : 'I paid this share'}</button></div>}
      {share.payment_status === 'Pending Verification' && <p className="muted">Awaiting admin verification. Reporting a payment does not transfer money.</p>}
      {share.paid_on && <p className="muted">Verified paid on {share.paid_on}.</p>}
      <details className="rent-history"><summary>Payment history ({share.ledger.length})</summary><ol>{share.ledger.map(entry => <li key={entry.log_id}><strong>{entry.previous_status ? `${entry.previous_status} → ${entry.new_status}` : entry.new_status}</strong><span>{entry.note}</span><small>{entry.recorded_by} · {new Date(entry.created_at).toLocaleString('en-IN')}</small></li>)}</ol></details>
    </article>)}</div>
    {!shares.length && <article className="panel"><p className="muted">No rent month has been generated for your lease yet. Your admin can create one in the Rent ledger.</p></article>}
  </section>;
}
