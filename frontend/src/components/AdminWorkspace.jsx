import { useEffect, useState } from 'react';
import { request } from '../services/api';
import AdminUtilities from './AdminUtilities';
import AdminSharedLeases from './AdminSharedLeases';
import AdminRentLedger from './AdminRentLedger';
import TicketTimeline from './TicketTimeline';
import './admin-workspace.css';
import './admin-tickets.css';

const blankUser = { tenant_name: '', t_email: '', t_dob: '', t_phone_no: '', password: '' };
const blankTicket = { tenant_id: '', unit_id: '', category: '', description: '' };
const adminPages = ['dashboard', 'users', 'leases', 'rent', 'tickets', 'utilities'];

export default function AdminWorkspace({ logout }) {
  const [page, setPage] = useState(() => {
    const saved = sessionStorage.getItem('apartmenthub_admin_page');
    return adminPages.includes(saved) ? saved : 'dashboard';
  });
  const [stats, setStats] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [ticketSummary, setTicketSummary] = useState({ total: 0, categories: [] });
  const [ticketUsers, setTicketUsers] = useState([]);
  const [ticketDraft, setTicketDraft] = useState(blankTicket);
  const [ticketFilter, setTicketFilter] = useState(() => sessionStorage.getItem('apartmenthub_ticket_filter') === 'all' ? 'all' : 'active');
  const [ticketBusy, setTicketBusy] = useState(false);
  const [workingTicketId, setWorkingTicketId] = useState(null);
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(blankUser);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const loadDashboard = async () => { try { setStats(await request('/admin/dashboard')); } catch (error) { setMessage(error.message); } };
  const loadUsers = async (query = search) => { try { setUsers(await request(`/admin/users?search=${encodeURIComponent(query)}`)); } catch (error) { setMessage(error.message); } };
  const loadTickets = async () => {
    const [allTickets, summary, allUsers] = await Promise.allSettled([request('/admin/tickets'), request('/admin/tickets/summary'), request('/admin/users')]);
    if (allTickets.status === 'fulfilled') setTickets(allTickets.value);
    if (summary.status === 'fulfilled') setTicketSummary(summary.value);
    if (allUsers.status === 'fulfilled') setTicketUsers(allUsers.value);
    const failures = [allTickets, summary, allUsers].filter(result => result.status === 'rejected');
    if (failures.length) setMessage(failures.map(result => result.reason.message).join(' '));
  };
  useEffect(() => { sessionStorage.setItem('apartmenthub_admin_page', page); }, [page]);
  useEffect(() => { sessionStorage.setItem('apartmenthub_ticket_filter', ticketFilter); }, [ticketFilter]);
  useEffect(() => {
    if (page === 'dashboard') loadDashboard();
    if (page === 'users') loadUsers('');
    if (page === 'tickets') loadTickets();
  }, [page]);
  useEffect(() => {
    if (page !== 'dashboard') return;
    const interval = setInterval(loadDashboard, 10000);
    window.addEventListener('focus', loadDashboard);
    return () => { clearInterval(interval); window.removeEventListener('focus', loadDashboard); };
  }, [page]);
  useEffect(() => {
    if (page !== 'tickets') return;
    const interval = setInterval(loadTickets, 10000);
    window.addEventListener('focus', loadTickets);
    return () => { clearInterval(interval); window.removeEventListener('focus', loadTickets); };
  }, [page]);

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
  async function advanceTicket(ticket, note) {
    const next = { Open: 'In Progress', 'In Progress': 'Resolved', Resolved: 'Closed' }[ticket.status];
    if (!next) return;
    setWorkingTicketId(ticket.ticket_id);
    try {
      await request(`/admin/tickets/${ticket.ticket_id}/status`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: next, update_message: note }) });
      await Promise.all([loadTickets(), loadDashboard()]);
      setMessage(`Ticket #${ticket.ticket_id} moved to ${next} successfully.`);
      return true;
    } catch (error) { setMessage(error.message); return false; } finally { setWorkingTicketId(null); }
  }

  async function createTicket(event) {
    event.preventDefault(); setTicketBusy(true); setMessage('');
    try {
      const payload = {
        tenant_id: Number(ticketDraft.tenant_id),
        unit_id: ticketDraft.unit_id ? Number(ticketDraft.unit_id) : null,
        category: ticketDraft.category,
        description: ticketDraft.description.trim(),
      };
      await request('/admin/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      setTicketDraft(blankTicket);
      setTicketFilter('active');
      await Promise.all([loadTickets(), loadDashboard()]);
      setMessage('Maintenance ticket created successfully.');
    } catch (error) { setMessage(error.message); } finally { setTicketBusy(false); }
  }

  async function removeTicket(ticket) {
    if (!confirm(`Permanently delete ticket #${ticket.ticket_id} for ${ticket.tenant_name}? This also removes its update history.`)) return;
    setWorkingTicketId(ticket.ticket_id); setMessage('');
    try {
      await request(`/admin/tickets/${ticket.ticket_id}`, { method: 'DELETE' });
      await Promise.all([loadTickets(), loadDashboard()]);
      setMessage(`Ticket #${ticket.ticket_id} deleted successfully.`);
    } catch (error) { setMessage(error.message); } finally { setWorkingTicketId(null); }
  }

  return <div className="admin-shell">
    <aside className="admin-sidebar"><div className="brand"><span className="brand-mark">⌂</span>ApartmentHub</div><p className="admin-label">ADMIN PANEL</p><button className={page === 'dashboard' ? 'active' : ''} onClick={() => setPage('dashboard')}>Dashboard</button><button className={page === 'users' ? 'active' : ''} onClick={() => setPage('users')}>Tenant management</button><button className={page === 'leases' ? 'active' : ''} onClick={() => setPage('leases')}>Shared leases</button><button className={page === 'rent' ? 'active' : ''} onClick={() => setPage('rent')}>Rent ledger</button><button className={page === 'tickets' ? 'active' : ''} onClick={() => setPage('tickets')}>Maintenance tickets</button><button className={page === 'utilities' ? 'active' : ''} onClick={() => setPage('utilities')}>Utility ledger</button><button className="admin-signout" onClick={logout}>Sign out</button></aside>
    <main className="admin-main" key={page}>
      {page === 'users' && <div className="admin-user-refresh"><button type="button" className="soft-button" onClick={() => loadUsers(search)}>Refresh tenants</button></div>}
      {page === 'dashboard' && <section><p className="eyebrow">ADMIN OVERVIEW</p><h1>Dashboard</h1><p className="muted">A live summary of the records currently in ApartmentHub.</p><button className="soft-button refresh-button" onClick={loadDashboard}>Refresh data</button><div className="admin-stat-grid"><Stat label="Total users" value={stats?.total_users} /><Stat label="Pending maintenance" value={stats?.pending_tickets} /><Stat label="Resolved tickets" value={stats?.resolved_tickets} /><Stat label="Deposits held / partial" value={stats?.pending_deposits} /><Stat label="Lease agreements" value={stats?.active_leases} /></div><div className="admin-percentage-grid"><PercentageStat label="Rent still unpaid" percentage={stats?.rent_unpaid_percentage} detail={`${stats?.unpaid_rent_count ?? 0} of ${stats?.active_leases ?? 0} leases`} /><PercentageStat label="Utility bills unpaid" percentage={stats?.utility_unpaid_percentage} detail={`${stats?.unpaid_utility_tenants ?? 0} of ${stats?.billed_tenants ?? 0} billed tenants`} /><PercentageStat label="Maintenance unresolved" percentage={stats?.unresolved_ticket_percentage} detail={`${stats?.pending_tickets ?? 0} of ${stats?.total_tickets ?? 0} tickets`} /></div></section>}
      {page === 'users' && <section><div className="admin-title"><div><p className="eyebrow">TENANT DIRECTORY</p><h1>Tenant management</h1><p className="muted">Search by name or email, then update, add or remove the tenant record.</p></div><button className="primary compact" onClick={clearForm}>+ Add tenant</button></div><form className="tenant-search" onSubmit={event => { event.preventDefault(); loadUsers(search); }}><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search tenant name or email" /><button className="soft-button">Search</button></form><div className="tenant-layout"><article className="panel tenant-list"><div className="list-heading"><strong>{users.length} tenant{users.length === 1 ? '' : 's'}</strong><button className="text-button" onClick={() => { setSearch(''); loadUsers(''); }}>Clear</button></div>{users.map(user => <button className={`tenant-row ${selected?.tenant_id === user.tenant_id ? 'selected' : ''}`} key={user.tenant_id} onClick={() => selectUser(user)}><span className="tenant-avatar">{user.tenant_name.charAt(0)}</span><span><strong>{user.tenant_name}</strong><small>{user.t_email}</small></span></button>)}{!users.length && <p className="muted">No matching tenants found.</p>}</article><article className="panel tenant-form-card"><p className="eyebrow">{selected ? `EDIT TENANT #${selected.tenant_id}` : 'NEW TENANT'}</p><h2>{selected ? selected.tenant_name : 'Create tenant'}</h2><form onSubmit={saveUser}><label>Full name<input required name="tenant_name" value={form.tenant_name} onChange={updateForm} /></label><label>Email address<input required type="email" name="t_email" value={form.t_email} onChange={updateForm} /></label><div className="form-grid"><label>Date of birth<input required type="date" name="t_dob" value={form.t_dob} onChange={updateForm} /></label><label>Phone number<input required name="t_phone_no" value={form.t_phone_no} onChange={updateForm} /></label></div><label>{selected ? 'New password (leave blank to keep current)' : 'Password'}<input required={!selected} minLength="8" type="password" name="password" value={form.password} onChange={updateForm} /></label>{message && <p className={message.includes('successfully') ? 'success-text' : 'error'}>{message}</p>}<div className="actions"><button className="primary" disabled={busy}>{busy ? 'Saving...' : selected ? 'Save changes' : 'Create tenant'}</button>{selected && <button type="button" className="danger-button" onClick={removeUser}>Delete tenant</button>}</div></form></article></div></section>}
      {page === 'tickets' && <AdminTicketsPage
        tickets={tickets} summary={ticketSummary} users={ticketUsers}
        draft={ticketDraft} setDraft={setTicketDraft} filter={ticketFilter} setFilter={setTicketFilter}
        busy={ticketBusy} workingTicketId={workingTicketId} message={message}
        onCreate={createTicket} onAdvance={advanceTicket} onDelete={removeTicket} onRefresh={loadTickets}
      />}
      {page === 'utilities' && <AdminUtilities />}
      {page === 'rent' && <AdminRentLedger />}
      {page === 'leases' && <AdminSharedLeases />}
      {message && page === 'dashboard' && <p className="error banner">{message}</p>}
    </main>
  </div>;
}

function Stat({ label, value }) { return <article><p>{label}</p><strong>{value ?? '—'}</strong></article>; }

function AdminTicketsPage({ tickets, summary, users, draft, setDraft, filter, setFilter, busy, workingTicketId, message, onCreate, onAdvance, onDelete, onRefresh }) {
  const [notes, setNotes] = useState({});
  const activeTickets = tickets.filter(ticket => ticket.status !== 'Closed');
  const visibleTickets = filter === 'active' ? activeTickets : tickets;
  const change = event => setDraft(current => ({ ...current, [event.target.name]: event.target.value }));

  return <section>
    <div className="admin-title">
      <div><p className="eyebrow">MAINTENANCE DESK</p><h1>Maintenance tickets</h1><p className="muted">Move requests from Open to In Progress, Resolved, then Closed. Each change appears in the timeline.</p></div>
      <button className="soft-button" onClick={onRefresh}>Refresh tickets</button>
    </div>
    <TicketCategoryChart summary={summary} />
    <form className="panel admin-ticket-create" onSubmit={onCreate}>
      <div><p className="eyebrow">NEW REQUEST</p><h2>Create a maintenance ticket</h2></div>
      <div className="admin-ticket-fields">
        <label>Tenant
          <select name="tenant_id" value={draft.tenant_id} onChange={change} required>
            <option value="">Choose a tenant</option>
            {users.map(user => <option value={user.tenant_id} key={user.tenant_id}>{user.tenant_name} · {user.t_email}</option>)}
          </select>
        </label>
        <label>Unit ID <small>(optional when tenant has a lease)</small>
          <input name="unit_id" type="number" min="1" value={draft.unit_id} onChange={change} placeholder="Use tenant’s linked unit" />
        </label>
        <label>Category
          <select name="category" value={draft.category} onChange={change} required>
            <option value="">Choose a category</option>
            {['Plumbing', 'Electrical', 'Appliance', 'Internet', 'Cleaning', 'Other'].map(category => <option key={category}>{category}</option>)}
          </select>
        </label>
        <label className="admin-ticket-description">Issue description
          <textarea name="description" value={draft.description} onChange={change} minLength="10" required placeholder="Describe the issue and its location." />
        </label>
      </div>
      <button className="primary compact" disabled={busy}>{busy ? 'Creating...' : 'Create ticket'}</button>
    </form>
    {message && <p className={message.includes('successfully') ? 'success-text' : 'error'} role="status">{message}</p>}
    <div className="admin-ticket-list-head">
      <h2>{filter === 'active' ? 'Active requests' : 'All requests'}</h2>
      <div className="admin-ticket-filters" aria-label="Ticket filters">
        <button className={filter === 'active' ? 'selected' : ''} onClick={() => setFilter('active')}>Active ({activeTickets.length})</button>
        <button className={filter === 'all' ? 'selected' : ''} onClick={() => setFilter('all')}>All ({tickets.length})</button>
      </div>
    </div>
    <div className="admin-ticket-grid">
      {visibleTickets.map(ticket => <article className="panel admin-ticket-card" key={ticket.ticket_id}>
        <div className="ticket-card-head"><span className={`badge ${ticket.status === 'Closed' || ticket.status === 'Resolved' ? 'closed' : 'unpaid'}`}>{ticket.status}</span><small>Ticket #{ticket.ticket_id}</small></div>
        <h2>{ticket.category}</h2><p>{ticket.description}</p>
        <div className="ticket-meta"><span><strong>{ticket.tenant_name}</strong><small>{ticket.tenant_email}</small></span><span>Unit #{ticket.unit_id}</span></div>
        <TicketTimeline ticket={ticket} />
        {ticket.status !== 'Closed' && <label className="ticket-note">Update note (optional)<textarea value={notes[ticket.ticket_id] ?? ''} maxLength="1000" placeholder="What changed?" onChange={event => setNotes(current => ({ ...current, [ticket.ticket_id]: event.target.value }))} /></label>}
        <div className="admin-ticket-actions">
          {ticket.status !== 'Closed' && <button className="primary compact" disabled={workingTicketId === ticket.ticket_id} onClick={async () => { if (await onAdvance(ticket, notes[ticket.ticket_id] ?? '')) setNotes(current => ({ ...current, [ticket.ticket_id]: '' })); }}>{({ Open: 'Start work', 'In Progress': 'Mark resolved', Resolved: 'Close ticket' })[ticket.status]}</button>}
          <button className="danger-button" disabled={workingTicketId === ticket.ticket_id} onClick={() => onDelete(ticket)}>Delete ticket</button>
        </div>
      </article>)}
      {!visibleTickets.length && <article className="panel"><p className="muted">No {filter === 'active' ? 'active' : ''} maintenance tickets found.</p></article>}
    </div>
  </section>;
}

function PercentageStat({ label, percentage, detail }) {
  const value = percentage ?? 0;
  return <article className="percentage-stat"><div className="percentage-ring" style={{ '--percentage': `${value * 3.6}deg` }}><strong>{value}%</strong></div><div><p>{label}</p><span>{detail}</span></div></article>;
}

function TicketCategoryChart({ summary }) {
  const colors = ['#85586f', '#d0b8a8', '#c7905b', '#5d3b4b', '#ba8798', '#8f9a73'];
  const categories = summary?.categories ?? [];
  let current = 0;
  const segments = categories.map((item, index) => {
    const start = current;
    current += item.percentage * 3.6;
    return `${colors[index % colors.length]} ${start}deg ${current}deg`;
  });
  return <article className="ticket-chart panel"><div className="ticket-pie" style={{ background: categories.length ? `conic-gradient(${segments.join(', ')})` : '#dfd3c3' }}><div><strong>{summary?.total ?? 0}</strong><span>tickets</span></div></div><div className="ticket-chart-copy"><p className="eyebrow">TICKET MIX</p><h2>What residents need help with</h2><div className="ticket-legend">{categories.map((item, index) => <span key={item.category}><i style={{ background: colors[index % colors.length] }} />{item.category}<strong>{item.percentage}%</strong></span>)}{!categories.length && <p className="muted">No ticket categories to show yet.</p>}</div></div></article>;
}
