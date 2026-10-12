import { useEffect, useState } from 'react';
import { request } from '../services/api';
import './admin-workspace.css';
import './admin-tickets.css';

const blankUser = { tenant_name: '', t_email: '', t_dob: '', t_phone_no: '', password: '' };

export default function AdminWorkspace({ logout }) {
  const [page, setPage] = useState('dashboard');
  const [stats, setStats] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(blankUser);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const loadDashboard = async () => { try { setStats(await request('/admin/dashboard')); } catch (error) { setMessage(error.message); } };
  const loadUsers = async (query = search) => { try { setUsers(await request(`/admin/users?search=${encodeURIComponent(query)}`)); } catch (error) { setMessage(error.message); } };
  const loadTickets = async () => { try { setTickets(await request('/admin/tickets/active')); } catch (error) { setMessage(error.message); } };
  useEffect(() => { loadDashboard(); }, []);
  useEffect(() => { if (page === 'users') loadUsers(''); if (page === 'tickets') loadTickets(); }, [page]);

  function selectUser(user) {
    setSelected(user); setForm({ tenant_name: user.tenant_name, t_email: user.t_email, t_dob: user.t_dob, t_phone_no: user.t_phone_no, password: '' }); setMessage('');
  }
  function clearForm() { setSelected(null); setForm(blankUser); setMessage(''); }
  function updateForm(event) { setForm(current => ({ ...current, [event.target.name]: event.target.value })); }
  async function saveUser(event) {
    event.preventDefault(); setBusy(true); setMessage('');
    const payload = { ...form };
    if (!payload.password) delete payload.password;
    try {
      if (selected) await request(`/admin/users/${selected.tenant_id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      else await request('/admin/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) });
      setMessage(selected ? 'Tenant updated successfully.' : 'Tenant created successfully.'); clearForm(); loadUsers(); loadDashboard();
    } catch (error) { setMessage(error.message); } finally { setBusy(false); }
  }
  async function removeUser() {
    if (!selected || !confirm(`Delete ${selected.tenant_name}?`)) return;
    try { await request(`/admin/users/${selected.tenant_id}`, { method: 'DELETE' }); setMessage('Tenant deleted successfully.'); clearForm(); loadUsers(); loadDashboard(); } catch (error) { setMessage(error.message); }
  }
  async function closeTicket(ticket) {
    if (!confirm(`Close ticket #${ticket.ticket_id} raised by ${ticket.tenant_name}?`)) return;
    try {
      await request(`/admin/tickets/${ticket.ticket_id}/close`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ update_message: 'Closed by administrator' }) });
      setMessage(`Ticket #${ticket.ticket_id} closed successfully.`); loadTickets(); loadDashboard();
    } catch (error) { setMessage(error.message); }
  }

  return <div className="admin-shell">
    <aside className="admin-sidebar"><div className="brand"><span className="brand-mark">⌂</span>ApartmentHub</div><p className="admin-label">ADMIN PANEL</p><button className={page === 'dashboard' ? 'active' : ''} onClick={() => setPage('dashboard')}>Dashboard</button><button className={page === 'users' ? 'active' : ''} onClick={() => setPage('users')}>Tenant management</button><button className={page === 'tickets' ? 'active' : ''} onClick={() => setPage('tickets')}>Maintenance tickets</button><button className="admin-signout" onClick={logout}>Sign out</button></aside>
    <main className="admin-main">
      {page === 'dashboard' && <section><p className="eyebrow">ADMIN OVERVIEW</p><h1>Dashboard</h1><p className="muted">A live summary of the records currently in ApartmentHub.</p><button className="soft-button refresh-button" onClick={loadDashboard}>Refresh data</button><div className="admin-stat-grid"><Stat label="Total users" value={stats?.total_users} /><Stat label="Pending maintenance" value={stats?.pending_tickets} /><Stat label="Resolved tickets" value={stats?.resolved_tickets} /><Stat label="Deposit payments pending" value={stats?.pending_deposits} /><Stat label="Lease agreements" value={stats?.active_leases} /></div></section>}
      {page === 'users' && <section><div className="admin-title"><div><p className="eyebrow">TENANT DIRECTORY</p><h1>Tenant management</h1><p className="muted">Search by name or email, then update, add or remove the tenant record.</p></div><button className="primary compact" onClick={clearForm}>+ Add tenant</button></div><form className="tenant-search" onSubmit={event => { event.preventDefault(); loadUsers(search); }}><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search tenant name or email" /><button className="soft-button">Search</button></form><div className="tenant-layout"><article className="panel tenant-list"><div className="list-heading"><strong>{users.length} tenant{users.length === 1 ? '' : 's'}</strong><button className="text-button" onClick={() => { setSearch(''); loadUsers(''); }}>Clear</button></div>{users.map(user => <button className={`tenant-row ${selected?.tenant_id === user.tenant_id ? 'selected' : ''}`} key={user.tenant_id} onClick={() => selectUser(user)}><span className="tenant-avatar">{user.tenant_name.charAt(0)}</span><span><strong>{user.tenant_name}</strong><small>{user.t_email}</small></span></button>)}{!users.length && <p className="muted">No matching tenants found.</p>}</article><article className="panel tenant-form-card"><p className="eyebrow">{selected ? `EDIT TENANT #${selected.tenant_id}` : 'NEW TENANT'}</p><h2>{selected ? selected.tenant_name : 'Create tenant'}</h2><form onSubmit={saveUser}><label>Full name<input required name="tenant_name" value={form.tenant_name} onChange={updateForm} /></label><label>Email address<input required type="email" name="t_email" value={form.t_email} onChange={updateForm} /></label><div className="form-grid"><label>Date of birth<input required type="date" name="t_dob" value={form.t_dob} onChange={updateForm} /></label><label>Phone number<input required name="t_phone_no" value={form.t_phone_no} onChange={updateForm} /></label></div><label>{selected ? 'New password (leave blank to keep current)' : 'Password'}<input required={!selected} minLength="8" type="password" name="password" value={form.password} onChange={updateForm} /></label>{message && <p className={message.includes('successfully') ? 'success-text' : 'error'}>{message}</p>}<div className="actions"><button className="primary" disabled={busy}>{busy ? 'Saving...' : selected ? 'Save changes' : 'Create tenant'}</button>{selected && <button type="button" className="danger-button" onClick={removeUser}>Delete tenant</button>}</div></form></article></div></section>}
      {page === 'tickets' && <section><div className="admin-title"><div><p className="eyebrow">MAINTENANCE DESK</p><h1>Active maintenance tickets</h1><p className="muted">Close a ticket once the reported issue has been handled. The action is saved in the ticket update log.</p></div><button className="soft-button" onClick={loadTickets}>Refresh tickets</button></div>{message && <p className={message.includes('successfully') ? 'success-text' : 'error'}>{message}</p>}<div className="admin-ticket-grid">{tickets.map(ticket => <article className="panel admin-ticket-card" key={ticket.ticket_id}><div className="ticket-card-head"><span className="badge unpaid">{ticket.status}</span><small>Ticket #{ticket.ticket_id}</small></div><h2>{ticket.category}</h2><p>{ticket.description}</p><div className="ticket-meta"><span><strong>{ticket.tenant_name}</strong><small>{ticket.tenant_email}</small></span><span>Unit #{ticket.unit_id}</span></div><button className="primary compact" onClick={() => closeTicket(ticket)}>Close ticket</button></article>)}{!tickets.length && <article className="panel"><p className="muted">There are no active maintenance tickets.</p></article>}</div></section>}
      {message && page === 'dashboard' && <p className="error banner">{message}</p>}
    </main>
  </div>;
}

function Stat({ label, value }) { return <article><p>{label}</p><strong>{value ?? '—'}</strong></article>; }
