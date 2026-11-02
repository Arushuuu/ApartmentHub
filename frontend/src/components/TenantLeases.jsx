import './shared-leases.css';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(value ?? 0);

export default function TenantLeases({ leases, onRefresh }) {
  return <section className="tenant-leases"><div className="page-title"><div><p className="eyebrow">YOUR HOME</p><h1>My leases & deposits</h1><p className="muted">See everyone on your lease and how the security deposit is shared. Monthly rent shares appear in Rent after an admin generates the month.</p></div><button type="button" className="soft-button" onClick={onRefresh}>Refresh</button></div>
    {leases.map(lease => <article className="panel tenant-shared-lease" key={lease.lease_id}>
      <p className="eyebrow">LEASE #{lease.lease_id}</p><h2>{lease.unit_label ?? `Unit #${lease.unit_id}`}</h2>
      <div className="tenant-lease-facts"><span><small>Full monthly rent</small><strong>{money(lease.monthly_rent)}</strong></span><span><small>Starts</small><strong>{lease.start_date}</strong></span><span><small>Ends</small><strong>{lease.end_date}</strong></span></div>
      <div className="tenant-lease-section"><h3>Signatories</h3><div className="shared-pills">{(lease.signatories ?? []).map(person => <span key={person.tenant_id}>{person.tenant_name}{person.tenant_id === lease.primary_tenant_id ? ' · Primary' : ''}</span>)}</div></div>
      <div className="tenant-lease-section"><h3>Security deposit</h3>{lease.deposit ? <><p className="muted">Total recorded: {money(lease.deposit.amount_held)} · {lease.deposit.refund_status}</p><p className="shared-balance">Remaining refundable: <strong>{lease.deposit.needs_reconciliation ? 'Admin reconciliation needed' : money(lease.deposit.remaining_balance)}</strong></p>{Number(lease.deposit.unattributed_amt) > 0 && <p className="muted">{money(lease.deposit.unattributed_amt)} has not yet been attributed to a signatory.</p>}
        <div className="tenant-contribution-list">{lease.deposit.contributions.map(row => <div key={row.tenant_id}><strong>{row.tenant_name}</strong><span>Contributed {money(row.contributed_amt)}</span><span>Refunded {row.refunded_amt === null ? 'unknown' : money(row.refunded_amt)}</span></div>)}</div>
        <details className="shared-history"><summary>Deposit history ({lease.deposit.ledger.length})</summary><ol>{lease.deposit.ledger.map(entry => <li key={entry.entry_id}><strong>{entry.action}</strong> · {entry.tenant_name} · {entry.amount === null ? 'amount unknown' : money(entry.amount)}<small>{entry.note} · {entry.recorded_by}</small></li>)}</ol></details>
      </> : <p className="muted">No deposit contributions have been recorded yet.</p>}</div>
    </article>)}
    {!leases.length && <article className="panel"><p className="muted">No lease linked yet. Open Profile setup to add one.</p></article>}
  </section>;
}
