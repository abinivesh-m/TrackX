// frontend/src/components/common/RecentActivity.tsx
//
// Detection log - the tail of real ANPR observations coming off the
// pipeline, styled as an operational event log (monospace plate/time,
// dense rows) rather than floating gradient-icon cards.

import React from 'react'
import { Activity } from 'lucide-react'
import type { Observation } from '@/types'

interface RecentActivityProps {
  observations: Observation[]
}

const RecentActivity: React.FC<RecentActivityProps> = ({ observations }) => {
  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="label-caps flex items-center gap-2">
          <Activity size={13} />
          Detection Log
        </h3>
        <span className="live-dot is-live" />
      </div>

      <div>
        {observations.length === 0 ? (
          <div className="text-center py-10 text-muted">
            <Activity size={28} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">No detections yet</p>
          </div>
        ) : (
          observations.slice(0, 5).map((obs) => (
            <div
              key={obs.id}
              className="flex items-center gap-3 px-4 py-2.5 border-b border-border last:border-b-0 hover:bg-surface-light"
            >
              <span className="live-dot flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-white font-data truncate">
                  {obs.plate_text || 'UNREAD'}
                </p>
                <p className="text-[11px] text-muted font-data">{obs.camera_id}</p>
              </div>
              <div className="text-[11px] text-muted font-data flex-shrink-0">
                {formatDate(obs.timestamp)}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default RecentActivity
