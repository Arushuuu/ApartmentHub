import { useCallback, useEffect, useState } from 'react';
import { request } from '../services/api';
import './rent-ledger.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);
const monthLabel = value => new Date(`${value.slice(0, 7)}-01T12:00:00`).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
const thisMonth = () => { const now = new Date(); return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`; };

export default function AdminRentLedger() {
  const [payments, setPayments] = useState([]);
  const [month, setMonth] = useState(thisMonth);
  const [search, setSearch] = useState('');
  const [notes, setNotes] = useState({});
  const [busy, setBusy] = useState(false);
  const [working, setWorking] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setPayments(await request('/admin/rent/months')); setError(''); }
    catch (caught) { setError(caught.message); }
  }, []);
  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    window.addEventListener('focus', load);
    return () => { clearInterval(interval); window.removeEventListener('focus', load); };
  }, [load]);

  async function generate(event) {
    event.preventDefault(); setBusy(true); setMessage(''); setError('');
    try {
      const result = await request('/admin/rent/months', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ billing_month: `${month}-01` }) });
      setMessage(`${result.created} rent month${result.created === 1 ? '' : 's'} created; ${result.existing} already existed.`);
      await load();
    } catch (caught) { setError(caught.message); }
    finally { setBusy(false); }
  }

  async function changeStatus(share, status) {
    setWorking(share.share_id); setMessage(''); setError('');
    try {
      await request(`/admin/rent/shares/${share.share_id}/status`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ payment_status: status, note: notes[share.share_id] ?? '' }) });
      setNotes(current => ({ ...current, [share.share_id]: '' }));
      setMessage(`${share.tenant_name}'s rent share is now ${status}.`);
      await load();
    } catch (caught) { setError(caught.message); }
    finally { setWorking(null); }
  }

  const filtered = payments.filter(payment => `${payment.billing_month} ${payment.lease_id} ${payment.unit_label} ${payment.shares.map(share => share.tenant_name).join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="rent-page"><div className="admin-title"><div><p className="eyebrow">RENTAL RECORDS</p><h1>Rent ledger</h1><p className="muted">Split monthly rent among the signatories on each lease, then verify payments made outside ApartmentHub.</p></div><button className="soft-button" onClick={load}>Refresh</button></div>
    <form className="panel rent-generate" onSubmit={generate}><div><h2>Generate monthly shares</h2><p className="muted">Creates one bill per lease active during that month. The full monthly rent is split exactly to the cent; existing months are left unchanged.</p></div><label>Billing month<input type="month" required value={month} onChange={event => setMonth(event.target.value)} /></label><button className="primary compact" disabled={busy}>{busy ? 'Creating...' : 'Generate month'}</button></form>
    {message && <p className="success-text" role="status">{message}</p>}
    {error && <p className="error banner" role="alert">{error}</p>}
    <label className="rent-search">Search lease, unit, month or tenant<input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search rent records" /></label>
    <p className="muted">{filtered.length} monthly record{filtered.length === 1 ? '' : 's'}</p>
    <div className="rent-admin-list">{filtered.map(payment => <article className="panel rent-admin-card" key={payment.payment_id}>
      <div className="rent-card-head"><div><p className="eyebrow">{monthLabel(payment.billing_month)} · LEASE #{payment.lease_id}</p><h2>{payment.unit_label}</h2><p className="muted">Full rent {money(payment.amount)} · {payment.shares.length} share{payment.shares.length === 1 ? '' : 's'}</p></div><span className={`badge ${payment.payment_status === 'Paid' ? 'paid' : 'unpaid'}`}>{payment.payment_status}</span></div>
      <div className="rent-share-list">{payment.shares.map(share => <div className="rent-share-row" key={share.share_id}>
        <div className="rent-share-head"><strong>{share.tenant_name}</strong><strong>{money(share.owed_amt)}</strong><span className={`badge ${share.payment_status === 'Paid' ? 'paid' : share.payment_status === 'Pending Verification' ? 'pending-verification' : 'unpaid'}`}>{share.payment_status}</span></div>
        <div className="rent-admin-action"><label>Verification note (optional)<input maxLength="500" value={notes[share.share_id] ?? ''} onChange={event => setNotes(current => ({ ...current, [share.share_id]: event.target.value }))} placeholder="Payment reference or reason" /></label>{share.payment_status !== 'Paid' ? <button className="soft-button" disabled={working === share.share_id} onClick={() => changeStatus(share, 'Paid')}>Verify paid</button> : <button className="soft-button" disabled={working === share.share_id} onClick={() => changeStatus(share, 'Unpaid')}>Return to unpaid</button>}</div>
        <details className="rent-history"><summary>History ({share.ledger.length})</summary><ol>{share.ledger.map(entry => <li key={entry.log_id}><strong>{entry.previous_status ? `${entry.previous_status} → ${entry.new_status}` : entry.new_status}</strong><span>{entry.note}</span><small>{entry.recorded_by} · {new Date(entry.created_at).toLocaleString('en-IN')}</small></li>)}</ol></details>
      </div>)}</div>
    </article>)}</div>
    {!filtered.length && <article className="panel"><p className="muted">No rent records found. Generate a month above after the lease signatories are set.</p></article>}
  </section>;
}
