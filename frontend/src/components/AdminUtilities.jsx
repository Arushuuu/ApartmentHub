import { useCallback, useEffect, useState } from 'react';
import { request } from '../services/api';
import './utility-ledger.css';

const today = new Date().toISOString().slice(0, 10);
const nextWeek = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);

export default function AdminUtilities() {
  const [bills, setBills] = useState([]);
  const [units, setUnits] = useState([]);
  const [form, setForm] = useState({ unit_id: '', total_amount: '', bill_date: today, due_date: nextWeek });
  const [busy, setBusy] = useState(false);
  const [busyShare, setBusyShare] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadBills = useCallback(async () => {
    try { setBills(await request('/admin/utility-bills')); setError(''); }
    catch (caught) { setError(caught.message); }
  }, []);

  useEffect(() => {
    loadBills();
    request('/admin/apartment_units').then(setUnits).catch(caught => setError(caught.message));
    const interval = setInterval(loadBills, 10000);
    window.addEventListener('focus', loadBills);
    return () => { clearInterval(interval); window.removeEventListener('focus', loadBills); };
  }, [loadBills]);

  async function createBill(event) {
    event.preventDefault(); setBusy(true); setMessage(''); setError('');
    try {
      const bill = await request('/admin/utility-bills', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, unit_id: Number(form.unit_id), total_amount: form.total_amount }),
      });
      setForm(current => ({ ...current, total_amount: '' }));
      setMessage(`Bill #${bill.bill_id} split among ${bill.shares.length} tenant(s).`);
      await loadBills();
    } catch (caught) { setError(caught.message); } finally { setBusy(false); }
  }

  async function updateShare(share, status) {
    setBusyShare(share.share_id); setMessage(''); setError('');
    try {
      await request(`/admin/utility-shares/${share.share_id}/status`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_status: status }),
      });
      setMessage(`${share.tenant_name}'s share is now ${status.toLowerCase()}.`);
      await loadBills();
    } catch (caught) { setError(caught.message); } finally { setBusyShare(null); }
  }

  const allShares = bills.flatMap(bill => bill.shares);
  const paidCount = allShares.filter(share => share.payment_status === 'Paid').length;
  const pendingCount = allShares.filter(share => share.payment_status === 'Pending Verification').length;

  return <section className="utility-ledger-page">
    <div className="admin-title"><div><p className="eyebrow">SHARED LIVING</p><h1>Utility bills & ledger</h1><p className="muted">Split each bill equally across tenants with an active lease on its bill date. Changes appear automatically within 10 seconds.</p></div><button className="soft-button" onClick={loadBills}>Refresh</button></div>
    <div className="utility-summary"><article><strong>{bills.length}</strong><span>Bills</span></article><article><strong>{allShares.length}</strong><span>Tenant shares</span></article><article><strong>{paidCount}</strong><span>Paid</span></article><article><strong>{pendingCount}</strong><span>To verify</span></article></div>
    <form className="panel utility-create-form" onSubmit={createBill}>
      <div><p className="eyebrow">NEW UTILITY BILL</p><h2>Split a bill</h2></div>
      <div className="utility-create-fields">
        <label>Apartment unit<select required value={form.unit_id} onChange={event => setForm(current => ({ ...current, unit_id: event.target.value }))}><option value="">Choose a unit</option>{units.map(unit => <option key={unit.unit_id} value={unit.unit_id}>{unit.building_name} · Unit {unit.unit_no} (#{unit.unit_id})</option>)}</select></label>
        <label>Total amount (₹)<input required type="number" min="0.01" step="0.01" value={form.total_amount} onChange={event => setForm(current => ({ ...current, total_amount: event.target.value }))} /></label>
        <label>Bill date<input required type="date" value={form.bill_date} onChange={event => setForm(current => ({ ...current, bill_date: event.target.value }))} /></label>
        <label>Due date<input required type="date" min={form.bill_date} value={form.due_date} onChange={event => setForm(current => ({ ...current, due_date: event.target.value }))} /></label>
      </div>
      <button className="primary compact" disabled={busy}>{busy ? 'Splitting bill...' : 'Create & split bill'}</button>
    </form>
    {message && <p className="success-text" role="status">{message}</p>}
    {error && <p className="error banner" role="alert">{error}</p>}
    <div className="utility-bill-list">{bills.map(bill => <article className="panel utility-bill-card" key={bill.bill_id}>
      <div className="utility-bill-head"><div><p className="eyebrow">BILL #{bill.bill_id}</p><h2>{bill.unit_label}</h2><p className="muted">Billed {bill.bill_date} · Due {bill.due_date}</p></div><strong>{money(bill.total_amount)}</strong></div>
      <div className="utility-share-list">{bill.shares.map(share => <div className="utility-share" key={share.share_id}>
        <div className="utility-share-main"><div><strong>{share.tenant_name}</strong><small>Share #{share.share_id}</small></div><strong>{money(share.owed_amt)}</strong><span className={`badge ${share.payment_status === 'Paid' ? 'paid' : share.payment_status === 'Pending Verification' ? 'pending-verification' : 'unpaid'}`}>{share.payment_status}</span></div>
        <div className="utility-share-actions">
          {share.payment_status !== 'Paid' && <button className="soft-button" disabled={busyShare === share.share_id} onClick={() => updateShare(share, 'Paid')}>{share.payment_status === 'Pending Verification' ? 'Verify payment' : 'Mark paid'}</button>}
          {share.payment_status !== 'Unpaid' && <button className="soft-button" disabled={busyShare === share.share_id} onClick={() => updateShare(share, 'Unpaid')}>{share.payment_status === 'Pending Verification' ? 'Return to unpaid' : 'Reopen unpaid'}</button>}
        </div>
        <details className="utility-history"><summary>Payment history ({share.ledger.length})</summary><ol>{share.ledger.map(entry => <li key={entry.log_id}><strong>{entry.new_status}</strong> · {entry.recorded_by}<small>{entry.note} · {new Date(entry.created_at).toLocaleString()}</small></li>)}</ol></details>
      </div>)}</div>
    </article>)}{!bills.length && !error && <article className="panel"><p className="muted">No utility bills have been created yet.</p></article>}</div>
  </section>;
}
