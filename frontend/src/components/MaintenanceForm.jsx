import { useState } from 'react';
import { request } from '../services/api';

export default function MaintenanceForm({ onCreated }) {
  const [values, setValues] = useState({ unit_id: '', category: '', description: '' });
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const change = event => setValues(current => ({ ...current, [event.target.name]: event.target.value }));

  async function submit(event) {
    event.preventDefault(); setSaving(true); setMessage('');
    try {
      await request('/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ unit_id: values.unit_id ? Number(values.unit_id) : null, category: values.category, description: values.description }) });
      setValues({ unit_id: '', category: '', description: '' }); setMessage('Maintenance ticket created successfully.'); onCreated?.();
    } catch (error) { setMessage(error.message); } finally { setSaving(false); }
  }

  return <form className="panel request-form" onSubmit={submit}>
    <label>Apartment unit ID <small>(optional if your account has a lease)</small><input name="unit_id" type="number" min="1" value={values.unit_id} onChange={change} placeholder="Leave blank to use active lease" /></label>
    <label>Category<select name="category" value={values.category} onChange={change} required><option value="" disabled>Select a category</option><option>Plumbing</option><option>Electrical</option><option>Appliance</option><option>Internet</option><option>Other</option></select></label>
    <label>What needs attention?<textarea name="description" value={values.description} onChange={change} minLength="10" required placeholder="Describe the issue and its location." /></label>
    {message && <p className={message.startsWith('Maintenance ticket') ? 'success-text' : 'error'}>{message}</p>}
    <button className="primary compact" disabled={saving}>{saving ? 'Creating ticket...' : 'Raise maintenance ticket'}</button>
  </form>;
}
