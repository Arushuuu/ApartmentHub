import { useCallback, useEffect, useState } from 'react';
import { request } from '../services/api';
import RefreshButton from './RefreshButton';
import './shared-leases.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);
const today = new Date().toISOString().slice(0, 10);
const yearLater = new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

export default function AdminSharedLeases() {
  const [leases, setLeases] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [units, setUnits] = useState([]);
  const [selectedId, setSelectedId] = useState(() => Number(sessionStorage.getItem('apartmenthub_selected_lease')) || null);
  const [search, setSearch] = useState('');
  const [newLease, setNewLease] = useState({ unit_id: '', primary_tenant_id: '', start_date: today, end_date: yearLater, monthly_rent: '' });
  const [newSigner, setNewSigner] = useState('');
  const [contribution, setContribution] = useState({ tenant_id: '', amount: '' });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try { setLeases(await request('/admin/shared-leases')); setError(''); return true; }
    catch (caught) { setError(caught.message); return false; }
  }, []);

  const refreshAll = useCallback(async () => {
    const [leaseRows, userRows, unitRows] = await Promise.allSettled([
      request('/admin/shared-leases'), request('/admin/users'), request('/admin/apartment_units'),
    ]);
    if (leaseRows.status === 'fulfilled') setLeases(leaseRows.value);
    if (userRows.status === 'fulfilled') setTenants(userRows.value);
    if (unitRows.status === 'fulfilled') setUnits(unitRows.value);
    const failures = [leaseRows, userRows, unitRows].filter(result => result.status === 'rejected');
    setError(failures.map(result => result.reason.message).join(' '));
    return failures.length === 0;
  }, []);

  useEffect(() => {
    refreshAll();
    const interval = setInterval(load, 10000);
    window.addEventListener('focus', load);
    return () => { clearInterval(interval); window.removeEventListener('focus', load); };
  }, [load, refreshAll]);
  useEffect(() => { if (selectedId) sessionStorage.setItem('apartmenthub_selected_lease', String(selectedId)); }, [selectedId]);

  const filtered = leases.filter(lease => `${lease.lease_id} ${lease.unit_label} ${lease.signatories.map(tenant => tenant.tenant_name).join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  const selected = filtered.find(lease => lease.lease_id === selectedId) ?? filtered[0];

  async function mutate(path, payload, success, method = 'POST') {
    setBusy(true); setMessage(''); setError('');
    try {
      const result = await request(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      await load();
      setMessage(success);
      return result;
    } catch (caught) { setError(caught.message); return null; }
    finally { setBusy(false); }
  }

  async function createLease(event) {
    event.preventDefault();
    const created = await mutate('/admin/shared-leases', { ...newLease, unit_id: Number(newLease.unit_id), primary_tenant_id: Number(newLease.primary_tenant_id) }, 'Shared lease created.');
    if (created) { setSearch(''); setSelectedId(created.lease_id); setNewLease(current => ({ ...current, unit_id: '', primary_tenant_id: '', monthly_rent: '' })); }
  }

  async function addSigner(event) {
    event.preventDefault();
    if (!selected) return;
    const result = await mutate(`/admin/shared-leases/${selected.lease_id}/signatories`, { tenant_id: Number(newSigner) }, 'Co-signer added.');
    if (result) setNewSigner('');
  }

  async function addDepositContribution(event) {
    event.preventDefault();
    if (!selected) return;
    const result = await mutate(`/admin/shared-leases/${selected.lease_id}/contributions`, { tenant_id: Number(contribution.tenant_id), amount: contribution.amount }, 'Deposit amount recorded.');
    if (result) setContribution({ tenant_id: '', amount: '' });
  }

  async function recordRefund(event, tenantId) {
    event.preventDefault();
    const form = event.currentTarget;
    const amount = new FormData(form).get('amount');
    const result = await mutate(`/admin/shared-leases/${selected.lease_id}/refunds`, { tenant_id: tenantId, amount }, 'Refund recorded.');
    if (result) form.reset();
  }

  async function reconcile(event, tenantId) {
    event.preventDefault();
    const form = event.currentTarget;
    const refunded_amount = new FormData(form).get('refunded_amount');
    const result = await mutate(`/admin/shared-leases/${selected.lease_id}/reconcile-refund`, { tenant_id: tenantId, refunded_amount }, 'Historical refund amount reconciled.', 'PATCH');
    if (result) form.reset();
  }

  return <section className="shared-lease-admin">
    <div className="admin-title"><div><p className="eyebrow">RENTAL RECORDS</p><h1>Shared leases & deposits</h1><p className="muted">Manage co-signers, each tenant's deposit contribution, and an auditable refund history.</p></div><RefreshButton onRefresh={refreshAll} /></div>
    {message && <p className="success-text" role="status">{message}</p>}
    {error && <p className="error banner" role="alert">{error}</p>}
    <details className="panel shared-create"><summary>+ Create a shared lease</summary><form onSubmit={createLease}>
      <div className="shared-form-grid">
        <label>Apartment unit<select required value={newLease.unit_id} onChange={event => setNewLease(current => ({ ...current, unit_id: event.target.value }))}><option value="">Choose a unit</option>{units.map(unit => <option key={unit.unit_id} value={unit.unit_id}>{unit.building_name} · Unit {unit.unit_no}</option>)}</select></label>
        <label>First signatory<select required value={newLease.primary_tenant_id} onChange={event => setNewLease(current => ({ ...current, primary_tenant_id: event.target.value }))}><option value="">Choose a tenant</option>{tenants.map(tenant => <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.tenant_name} · {tenant.t_email}</option>)}</select></label>
        <label>Start date<input required type="date" value={newLease.start_date} onChange={event => setNewLease(current => ({ ...current, start_date: event.target.value }))} /></label>
        <label>End date<input required type="date" min={newLease.start_date} value={newLease.end_date} onChange={event => setNewLease(current => ({ ...current, end_date: event.target.value }))} /></label>
        <label>Full monthly rent (₹)<input required type="number" min="0.01" step="0.01" value={newLease.monthly_rent} onChange={event => setNewLease(current => ({ ...current, monthly_rent: event.target.value }))} /></label>
      </div><button className="primary compact" disabled={busy}>{busy ? 'Saving...' : 'Create lease'}</button>
    </form></details>
    <div className="shared-layout">
      <div className="panel shared-list"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search lease, unit or tenant" aria-label="Search leases" />
        <p className="shared-count">{filtered.length} lease{filtered.length === 1 ? '' : 's'}</p>
        {filtered.map(lease => <button key={lease.lease_id} className={`shared-list-row ${selected?.lease_id === lease.lease_id ? 'selected' : ''}`} onClick={() => setSelectedId(lease.lease_id)}><strong>{lease.unit_label}</strong><span>Lease #{lease.lease_id} · {lease.signatories.length} {lease.signatories.length === 1 ? 'signatory' : 'signatories'}</span></button>)}
      </div>
      {selected ? <div className="shared-detail">
        <article className="panel"><p className="eyebrow">LEASE #{selected.lease_id}</p><h2>{selected.unit_label}</h2><p className="muted">{selected.start_date} to {selected.end_date} · Full monthly rent {money(selected.monthly_rent)}</p>
          <h3>Signatories</h3><div className="shared-pills">{selected.signatories.map(tenant => <span key={tenant.tenant_id}>{tenant.tenant_name}{tenant.tenant_id === selected.primary_tenant_id ? ' · Primary' : ''}</span>)}</div>
          <form className="shared-inline-form" onSubmit={addSigner}><label>Add a co-signer<select required value={newSigner} onChange={event => setNewSigner(event.target.value)}><option value="">Choose a tenant</option>{tenants.filter(tenant => !selected.signatories.some(signer => signer.tenant_id === tenant.tenant_id)).map(tenant => <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.tenant_name} · {tenant.t_email}</option>)}</select></label><button className="soft-button" disabled={busy}>Add signer</button></form>
        </article>
        <article className="panel"><p className="eyebrow">SECURITY DEPOSIT</p><h2>{selected.deposit ? money(selected.deposit.amount_held) : 'No contributions yet'}</h2><p className="muted">Total contributions recorded · Status: {selected.deposit?.refund_status ?? 'Not started'}</p>
          {selected.deposit && <><p className="shared-balance">Remaining refundable: <strong>{selected.deposit.needs_reconciliation ? 'Needs reconciliation' : money(selected.deposit.remaining_balance)}</strong></p>{Number(selected.deposit.unattributed_amt) > 0 && <p className="shared-reconcile-note">{money(selected.deposit.unattributed_amt)} of this deposit has not been attributed to a signatory. Record their contribution below before issuing refunds.</p>}</>}
          <form className="shared-inline-form shared-contribution-form" onSubmit={addDepositContribution}><label>Signatory<select required value={contribution.tenant_id} onChange={event => setContribution(current => ({ ...current, tenant_id: event.target.value }))}><option value="">Choose a signatory</option>{selected.signatories.map(tenant => <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.tenant_name}</option>)}</select></label><label>Contribution / allocation (₹)<input required type="number" min="0.01" step="0.01" value={contribution.amount} onChange={event => setContribution(current => ({ ...current, amount: event.target.value }))} /></label><button className="primary compact" disabled={busy}>Record amount</button></form>
          {selected.deposit?.contributions.map(row => <div className="shared-contribution" key={row.tenant_id}><strong>{row.tenant_name}</strong><span>Contributed {money(row.contributed_amt)} · Refunded {row.refunded_amt === null ? 'unknown' : money(row.refunded_amt)}</span>
            {row.refunded_amt === null ? <form className="shared-inline-form" onSubmit={event => reconcile(event, row.tenant_id)}><label>Enter historical refund total (₹)<input name="refunded_amount" required type="number" min="0" step="0.01" max={row.contributed_amt} /></label><button className="soft-button" disabled={busy}>Reconcile</button></form>
              : Number(row.refundable_amt) > 0 && Number(selected.deposit.unattributed_amt) === 0 && <form className="shared-inline-form" onSubmit={event => recordRefund(event, row.tenant_id)}><label>Refund now (₹)<input name="amount" required type="number" min="0.01" step="0.01" max={row.refundable_amt} /></label><button className="soft-button" disabled={busy}>Record refund</button></form>}
          </div>)}
          {selected.deposit && <details className="shared-history"><summary>Deposit history ({selected.deposit.ledger.length})</summary><ol>{selected.deposit.ledger.map(entry => <li key={entry.entry_id}><strong>{entry.action}</strong> · {entry.tenant_name} · {entry.amount === null ? 'amount unknown' : money(entry.amount)}<small>{entry.note} · {entry.recorded_by}</small></li>)}</ol></details>}
        </article>
      </div> : <article className="panel"><p className="muted">No leases found. Create one above to begin.</p></article>}
    </div>
  </section>;
}
