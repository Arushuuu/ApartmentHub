import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import AdminWorkspace from './components/AdminWorkspace';
import MaintenanceForm from './components/MaintenanceForm';
import TicketTimeline from './components/TicketTimeline';
import TenantUtilities from './components/TenantUtilities';
import TenantLeases from './components/TenantLeases';
import TenantRent from './components/TenantRent';
import { request } from './services/api';

const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value ?? 0);

function Intro({ onStart }) {
  return <main className="intro-page">
    <div className="intro-photo" aria-hidden="true" />
    <h1 className="intro-title">ApartmentHub</h1>
    <div className="intro-credit">Arushi Shandilya<br />U25UV24T029019<br />CSE A 5th Sem</div>
    <button className="intro-start" onClick={onStart}>Get Started <span aria-hidden="true">→</span></button>
  </main>;
}

function Landing({ openAuth, backToWelcome }) {
  const scrollToAbout = () => document.getElementById('about-us')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  return <main className="landing-page">
    <section className="landing-hero">
      <div className="landing-image landing-image-hero" aria-hidden="true" />
      <div className="hero-quote"><p>“Home is not a place. It is a feeling of belonging.”</p><button className="story-about-button" onClick={scrollToAbout}>About us <span aria-hidden="true">↓</span></button></div>
    </section>
    <section className="about-section" id="about-us">
      <div className="landing-image landing-image-about" aria-hidden="true" />
      <article className="about-copy"><button className="about-back" onClick={backToWelcome}>← Back</button><p className="eyebrow">ABOUT APARTMENTHUB</p><h1>A simpler rhythm for shared living.</h1><p>ApartmentHub brings rent, leases, shared utilities and maintenance requests into one thoughtful space. Tenants can follow what matters at home, while administrators keep every record organised and easy to manage.</p><p>Built for clarity, connection and a little more calm in everyday rental life.</p><button className="landing-cta" onClick={openAuth}>Sign in or create an account →</button></article>
    </section>
  </main>;
}

function Auth({ onSuccess, onBack }) {
  const [mode, setMode] = useState('login'); const [choice, setChoice] = useState('tenant'); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  async function submit(event) {
    event.preventDefault(); setLoading(true); setError(''); const form = new FormData(event.currentTarget);
    try {
      if (mode === 'signup') await request('/auth/signup', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tenant_name: form.get('name'), t_email: form.get('email'), password: form.get('password'), t_dob: form.get('dob'), t_phone_no: form.get('phone') }) });
      const login = await request('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ username: form.get('email'), password: form.get('password') }) });
      if (mode === 'login' && choice !== login.role) throw new Error(`This account is a ${login.role}. Select that role first.`);
      localStorage.setItem('apartmenthub_token', login.access_token); localStorage.setItem('apartmenthub_role', login.role); onSuccess(login.role, mode === 'signup');
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  }
  return <main className="auth-shell"><section className="auth-story"><div className="brand"><span className="brand-mark">⌂</span> ApartmentHub</div><div><p className="eyebrow">ONE HOME, ONE PLACE</p><h1>Every rental<br />detail, connected.</h1></div></section><section className="auth-panel"><div className="auth-card" key={mode}><button className="auth-back" onClick={onBack}>← Back</button><p className="eyebrow">WELCOME TO APARTMENTHUB</p><h2>{mode === 'login' ? 'Sign in' : 'Create a tenant account'}</h2><div className="role-picker">{['tenant','admin'].map(role => <button type="button" key={role} className={choice === role ? 'selected' : ''} onClick={() => setChoice(role)}><strong>{role}</strong></button>)}</div><form onSubmit={submit}>{mode === 'signup' && <><label>Full name<input name="name" required /></label><label>Date of birth<input name="dob" type="date" required /></label><label>Phone number<input name="phone" required /></label></>}<label>Email address<input name="email" type="email" required /></label><label>Password<input name="password" type="password" minLength="8" required /></label>{error && <p className="error">{error}</p>}<button className="primary" disabled={loading}>{loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'} →</button></form><p className="switch">{mode === 'login' ? 'New tenant?' : 'Already have an account?'} <button type="button" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); }}>{mode === 'login' ? 'Create one' : 'Sign in'}</button></p></div></section></main>;
}

function Setup({ done, embedded = false }) {
  const [message, setMessage] = useState('');
  async function submit(event) { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); for (const k of Object.keys(values)) if (!values[k]) values[k] = null; for (const k of ['existing_unit_id','base_rent','monthly_rent','deposit_amount']) if (values[k] !== null) values[k] = Number(values[k]); try { const result = await request('/account/setup', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(values) }); if (!result.created) throw new Error(result.message); setMessage('Saved successfully.'); } catch(e) { setMessage(e.message); } }
  const card = <div className="setup-card"><p className="eyebrow">OPTIONAL ACCOUNT SETUP</p><h1>Complete your rental profile.</h1><p className="muted">Add these details now or return later from the <strong>Profile setup</strong> section. You can create an apartment and lease, or link an existing unit.</p><form onSubmit={submit}><label>Existing apartment unit ID (optional)<input name="existing_unit_id" type="number" min="1" placeholder="Example: 3" /></label><p className="divider">OR CREATE A NEW APARTMENT</p><div className="form-grid"><label>Building name<input name="building_name" /></label><label>Unit number<input name="unit_no" /></label><label>Street<input name="street" /></label><label>Pincode<input name="pincode" /></label><label>Base rent<input name="base_rent" type="number" min="0" /></label></div><p className="divider">OPTIONAL LEASE</p><div className="form-grid"><label>Start date<input name="start_date" type="date" /></label><label>End date<input name="end_date" type="date" /></label><label>Monthly rent<input name="monthly_rent" type="number" min="0" /></label><label>Security deposit<input name="deposit_amount" type="number" min="0" /></label></div>{message && <p className={message.startsWith('Saved') ? 'success-text' : 'error'}>{message}</p>}<div className="actions"><button className="primary">Save profile details</button><button type="button" className="soft-button" onClick={done}>{embedded ? 'Back to overview' : 'Skip for now'}</button></div></form></div>;
  return embedded ? card : <main className="setup-page">{card}</main>;
}

function Shell({ title, tabs, active, setActive, children, logout }) { return <div className="app-shell"><aside><div className="brand"><span className="brand-mark">⌂</span>{title}</div><nav>{tabs.map(([id,label]) => <button key={id} className={active === id ? 'active' : ''} onClick={() => setActive(id)}>{label}</button>)}</nav><div className="side-foot"><button onClick={logout}>Sign out</button></div></aside><main className="dashboard-main" key={active}>{children}</main></div>; }
function Empty({ text }) { return <div className="empty">⌂<p>{text}</p></div>; }

function TenantHome({ logout }) {
  const [tab, setTab] = useState(() => {
    const saved = sessionStorage.getItem('apartmenthub_tenant_tab');
    return ['home', 'tickets', 'utilities', 'rent', 'lease', 'profile'].includes(saved) ? saved : 'home';
  }); const [data, setData] = useState({}); const [tickets, setTickets] = useState([]); const [leases, setLeases] = useState([]); const [leasesLoaded, setLeasesLoaded] = useState(false); const [shares, setShares] = useState([]); const [error, setError] = useState('');
  const load = async () => {
    const [dashboard, ticketRows, leaseRows, shareRows] = await Promise.allSettled([
      request('/account/dashboard'), request('/tickets/me'), request('/leases/me'), request('/utilities/me'),
    ]);
    if (dashboard.status === 'fulfilled') setData(dashboard.value);
    if (ticketRows.status === 'fulfilled') setTickets(ticketRows.value);
    if (leaseRows.status === 'fulfilled') { setLeases(leaseRows.value); setLeasesLoaded(true); }
    if (shareRows.status === 'fulfilled') setShares(shareRows.value);
    const failures = [dashboard, ticketRows, leaseRows, shareRows].filter(result => result.status === 'rejected');
    setError(failures.map(result => result.reason.message).join(' '));
  };
  useEffect(() => { load(); }, [tab]);
  useEffect(() => { sessionStorage.setItem('apartmenthub_tenant_tab', tab); }, [tab]);
  useEffect(() => {
    if (tab !== 'home' && tab !== 'tickets') return;
    const interval = setInterval(load, 10000);
    window.addEventListener('focus', load);
    return () => { clearInterval(interval); window.removeEventListener('focus', load); };
  }, [tab]);
  const profileComplete = leases.length > 0;
  useEffect(() => { if (profileComplete && tab === 'profile') setTab('home'); }, [profileComplete, tab]);
  const tenantTabs = [['home','Overview'],['tickets','Maintenance'],['utilities','Utilities'],['rent','Rent'],['lease','My lease']];
  if (leasesLoaded && !profileComplete) tenantTabs.push(['profile','Profile setup']);
  return <Shell title="ApartmentHub" tabs={tenantTabs} active={tab} setActive={setTab} logout={logout}>
    {error && <p className="error banner">{error}</p>}
    {tab === 'home' && <>
      <section className="welcome"><div><p className="eyebrow">YOUR HOME AT A GLANCE</p><h1>Hello, {data.tenant_name ?? 'there'}.</h1><p className="muted">Your apartment details, in one calm place.</p></div><button type="button" className="soft-button" onClick={load}>Refresh</button></section>
      <section className="stats"><article><p>Your monthly rent share</p><strong>{money(data.my_rent_share)}</strong></article><article><p>Utilities due</p><strong>{money(data.utilities_due)}</strong></article><article><p>Open requests</p><strong>{data.open_tickets ?? 0}</strong></article></section>
      <section className="two-column"><article className="panel"><p className="eyebrow">RECENT BILLS</p>{shares.slice(0,3).map(s => <div className="line-item" key={s.share_id}><span>Utility bill</span><strong>{money(s.owed_amt)}</strong><span className={`badge ${s.payment_status === 'Paid' ? 'paid' : s.payment_status === 'Pending Verification' ? 'pending-verification' : 'unpaid'}`}>{s.payment_status}</span></div>)}{!shares.length && <Empty text="No utility bills assigned yet." />}</article><article className="panel warm"><p className="eyebrow">MAINTENANCE</p><h2>{tickets[0]?.category ?? 'All clear'}</h2><p className="muted">{tickets[0]?.description ?? 'Create a ticket whenever something needs attention.'}</p></article></section>
    </>}
    {tab === 'tickets' && <><div className="page-title"><div><p className="eyebrow">HOME CARE</p><h1>Maintenance requests</h1><p className="muted">Follow each request from opening through completion.</p></div><button type="button" className="soft-button" onClick={load}>Refresh</button></div><MaintenanceForm onCreated={load} /><div className="tenant-ticket-list">{tickets.map(t => <article className="panel tenant-ticket-card" key={t.ticket_id}><div className="ticket-row"><div><strong>{t.category}</strong><p>{t.description}</p><small>Ticket #{t.ticket_id}</small></div><span className={`badge ${t.status === 'Closed' || t.status === 'Resolved' ? 'paid' : 'unpaid'}`}>{t.status}</span></div><TicketTimeline ticket={t} /></article>)}{!tickets.length && <article className="panel"><Empty text="No maintenance tickets yet." /></article>}</div></>}
    {tab === 'utilities' && <TenantUtilities shares={shares} onRefresh={load} />}
    {tab === 'rent' && <TenantRent />}
    {tab === 'lease' && <TenantLeases leases={leases} onRefresh={load} />}
    {tab === 'profile' && leasesLoaded && !profileComplete && <><div className="page-title"><div><p className="eyebrow">YOUR PROFILE</p><h1>Complete rental details</h1><p className="muted">You can safely add the optional apartment and lease information whenever you are ready.</p></div></div><Setup embedded done={() => setTab('home')} /></>}
  </Shell>;
}

function AdminHome({ logout }) {
  const [tables, setTables] = useState([]); const [table, setTable] = useState('tenants'); const [rows, setRows] = useState([]); const [draft, setDraft] = useState('{}'); const [error, setError] = useState('');
  const load = async name => { try { setRows(await request(`/admin/${name ?? table}`)); setError(''); } catch(e) { setError(e.message); } };
  useEffect(() => { request('/admin/tables').then(x => { setTables(x); load('tenants'); }).catch(e => setError(e.message)); }, []);
  async function save(method, id) { try { await request(`/admin/${table}${id ? `/${id}` : ''}`, { method, headers: {'Content-Type':'application/json'}, body: draft }); setDraft('{}'); load(); } catch(e) { setError(e.message); } }
  return <Shell title="ApartmentHub Admin" tabs={tables.map(t => [t,t.replaceAll('_',' ')])} active={table} setActive={x => { setTable(x); load(x); }} logout={logout}><section><div className="page-title"><div><p className="eyebrow">DATABASE CONTROL ROOM</p><h1>{table.replaceAll('_',' ')}</h1><p className="muted">View, edit, insert and remove the records in every project table.</p></div><button className="soft-button" onClick={() => load()}>Refresh</button></div>{error && <p className="error banner">{error}</p>}<article className="panel admin-table">{rows.map(row => <div className="admin-row" key={Object.values(row)[0]}><pre>{JSON.stringify(row, null, 2)}</pre><div><button className="soft-button" onClick={() => setDraft(JSON.stringify(row, null, 2))}>Edit</button><button className="danger-button" onClick={() => { if (confirm('Delete this record?')) save('DELETE', Object.values(row)[0]); }}>Delete</button></div></div>)}{!rows.length && <Empty text="No rows in this table." />}</article><article className="panel admin-editor"><p className="eyebrow">EDIT OR INSERT JSON</p><textarea value={draft} onChange={e => setDraft(e.target.value)} /><div className="actions"><button className="primary" onClick={() => save('POST')}>Insert record</button><button className="soft-button" onClick={() => { try { save('PATCH', Object.values(JSON.parse(draft))[0]); } catch { setError('Use valid JSON including the record ID.'); } }}>Update selected JSON</button></div></article></section></Shell>;
}

export default function AppV2() {
  const [role, setRole] = useState(localStorage.getItem('apartmenthub_role')); const [setup, setSetup] = useState(false); const [screen, setScreen] = useState('intro'); const [leaving, setLeaving] = useState(false); const transitionTimer = useRef(null); const transitionLock = useRef(false); const pendingSection = useRef(null); const token = localStorage.getItem('apartmenthub_token');
  useEffect(() => () => clearTimeout(transitionTimer.current), []);
  function jumpTo(top) {
    const root = document.documentElement;
    const oldBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = 'auto';
    window.scrollTo(0, top);
    root.style.scrollBehavior = oldBehavior;
  }
  useLayoutEffect(() => {
    if (screen !== 'landing' || pendingSection.current !== 'about-us') return;
    const about = document.getElementById('about-us');
    if (about) jumpTo(about.offsetTop);
    pendingSection.current = null;
  }, [screen]);
  function logout() {
    if (transitionLock.current) return;
    transitionLock.current = true;
    setLeaving(true);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    transitionTimer.current = setTimeout(() => {
      localStorage.removeItem('apartmenthub_token');
      localStorage.removeItem('apartmenthub_role');
      sessionStorage.removeItem('apartmenthub_admin_page');
      sessionStorage.removeItem('apartmenthub_tenant_tab');
      sessionStorage.removeItem('apartmenthub_ticket_filter');
      sessionStorage.removeItem('apartmenthub_selected_lease');
      jumpTo(0);
      setSetup(false);
      setScreen('auth');
      setRole(null);
      setLeaving(false);
      transitionLock.current = false;
    }, reducedMotion ? 0 : 300);
  }
  function goTo(next, section = null) {
    if (transitionLock.current || next === screen) return;
    pendingSection.current = section;
    transitionLock.current = true;
    setLeaving(true);
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    transitionTimer.current = setTimeout(() => {
      jumpTo(0);
      setScreen(next);
      setLeaving(false);
      transitionLock.current = false;
    }, reducedMotion ? 0 : 300);
  }
  if (!token || !role) return <div key={screen} className={`screen-stage${leaving ? ' is-leaving' : ''}`}>
    {screen === 'intro' ? <Intro onStart={() => goTo('landing')} /> : screen === 'auth' ? <Auth onBack={() => goTo('landing', 'about-us')} onSuccess={(newRole, needsSetup) => { setRole(newRole); setSetup(needsSetup); }} /> : <Landing openAuth={() => goTo('auth')} backToWelcome={() => goTo('intro')} />}
  </div>;
  let privatePage;
  if (setup && role === 'tenant') privatePage = <Setup done={() => setSetup(false)} />;
  else if (role === 'admin') privatePage = <AdminWorkspace logout={logout} />;
  else if (role === 'landlord') privatePage = <Shell title="ApartmentHub Landlord" tabs={[]} active="" setActive={() => {}} logout={logout}><article className="panel"><p className="eyebrow">COMING SOON</p><h1>Landlord workspace</h1><p className="muted">Maintenance ticket handling will be added here next.</p></article></Shell>;
  else privatePage = <TenantHome logout={logout} />;
  return <div className={`screen-stage${leaving ? ' is-leaving' : ''}`}>{privatePage}</div>;
}
