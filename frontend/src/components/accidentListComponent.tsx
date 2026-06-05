import { useEffect, useState } from 'react';
import getSelectionContext from './selectionContext';

interface AccidentRow {
  reference: string;
  num_ships: string;
  ships: string;
  solas_status: string;
  flags: string;
  ship_types: string;
  date: string;
  event: string;
  severity: string;
  geo_coordinates: string;
  place: string;
  location: string;
  num_reports: string;
  reporting_admins: string;
}

const FIELD_LABELS: [keyof AccidentRow, string][] = [
  ['reference',        'Reference'],
  ['date',             'Date / Time'],
  ['ships',            'Ships Involved'],
  ['num_ships',        'Number of Ships'],
  ['solas_status',     'SOLAS Status'],
  ['flags',            'Flag Administrations'],
  ['ship_types',       'Ship Types'],
  ['event',            'Casualty Event'],
  ['severity',         'Severity'],
  ['geo_coordinates',  'Coordinates'],
  ['place',            'Place'],
  ['location',         'Location'],
  ['num_reports',      'Investigation Reports'],
  ['reporting_admins', 'Reporting Administrations'],
];

function severityStyle(severity: string): { bg: string; color: string; label: string } {
  const s = severity.toLowerCase();
  if (s.includes('very serious')) return { bg: 'rgba(239,68,68,0.18)', color: '#ef4444', label: 'Very Serious' };
  if (s.includes('serious'))      return { bg: 'rgba(245,158,11,0.18)', color: '#f59e0b', label: 'Serious' };
  if (s.includes('incident'))     return { bg: 'rgba(96,165,250,0.18)', color: '#60a5fa', label: 'Incident' };
  if (s.includes('casualty'))     return { bg: 'rgba(245,158,11,0.18)', color: '#f59e0b', label: 'Casualty' };
  return { bg: 'rgba(156,163,175,0.18)', color: '#9ca3af', label: severity || 'Unknown' };
}

function firstVessel(ships: string): string {
  const first = ships.split(',')[0].trim();
  return first.replace(/\s*\(IMO\s*\d+\)/, '').trim();
}

function AccidentDetailModal({ accident, onClose }: { accident: AccidentRow; onClose: () => void }) {
  return (
    <div className='accident-modal-overlay' onClick={onClose}>
      <div className='accident-modal' onClick={e => e.stopPropagation()}>
        <div className='accident-modal-header'>
          <span className='accident-modal-title'>{accident.reference || 'Accident Detail'}</span>
          <button className='accident-modal-close' onClick={onClose}>×</button>
        </div>
        <div className='accident-modal-body'>
          <table className='accident-modal-table'>
            <tbody>
              {FIELD_LABELS.map(([key, label]) => {
                const val = accident[key];
                if (!val) return null;
                return (
                  <tr key={key}>
                    <td className='accident-modal-label'>{label}</td>
                    <td className='accident-modal-value'>{val}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AccidentListComponent() {
  const { currentCountry } = getSelectionContext();
  const [accidents, setAccidents] = useState<AccidentRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchedFor, setFetchedFor] = useState<string | null>(null);
  const [selected, setSelected] = useState<AccidentRow | null>(null);

  useEffect(() => {
    if (!currentCountry || currentCountry === fetchedFor) return;
    setLoading(true);
    setAccidents([]);
    fetch(`/api/accidents?country=${encodeURIComponent(currentCountry)}`)
      .then(r => r.json())
      .then(data => {
        setAccidents(data.data ?? []);
        setFetchedFor(currentCountry);
      })
      .catch(() => setAccidents([]))
      .finally(() => setLoading(false));
  }, [currentCountry]);

  if (!currentCountry) return null;

  return (
    <>
      <div className='accident-list-container'>
        <div className='accident-list-header'>
          Accident Reports
          {!loading && <span className='accident-list-count'> ({accidents.length})</span>}
        </div>
        {loading && <div className='accident-list-loading'>Loading…</div>}
        {!loading && accidents.length === 0 && (
          <div className='accident-list-loading'>No accident records for {currentCountry}</div>
        )}
        {accidents.map(acc => {
          const sev = severityStyle(acc.severity);
          const date = acc.date ? acc.date.slice(0, 10) : '—';
          const vessel = firstVessel(acc.ships);
          const type = acc.ship_types.split(',')[0].trim();
          return (
            <div
              key={acc.reference}
              className='accident-item'
              onClick={() => setSelected(acc)}
              title='Click to see full details'
            >
              <div className='accident-item-top'>
                <span className='accident-date'>{date}</span>
                <span
                  className='accident-severity-badge'
                  style={{ background: sev.bg, color: sev.color }}
                >
                  {sev.label}
                </span>
              </div>
              <div className='accident-vessel'>{vessel || '—'}</div>
              <div className='accident-meta'>
                {type && <span>{type}</span>}
                {acc.place && <span> · {acc.place}</span>}
              </div>
              {acc.event && <div className='accident-event'>{acc.event}</div>}
            </div>
          );
        })}
      </div>

      {selected && (
        <AccidentDetailModal accident={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
}

export default AccidentListComponent;
