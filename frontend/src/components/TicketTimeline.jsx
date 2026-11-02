import './ticket-timeline.css';

const dateLabel = value => value ? new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : 'Date unavailable';

export default function TicketTimeline({ ticket }) {
  return <details className="ticket-history">
    <summary>View timeline ({(ticket.updates ?? []).length + 1})</summary>
    <ol>
      <li><span className="history-dot" /><div><strong>Ticket opened</strong><small>{dateLabel(ticket.created_at)}</small></div></li>
      {(ticket.updates ?? []).map(update => <li key={update.log_id}>
        <span className="history-dot" />
        <div>
          <strong>{update.new_status ? `${update.previous_status} → ${update.new_status}` : 'Update added'}</strong>
          <p>{update.update_message}</p>
          <small>{update.updated_by} · {dateLabel(update.updated_timestamp)}</small>
        </div>
      </li>)}
    </ol>
  </details>;
}
