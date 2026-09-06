// frontend/src/components/common/RecentActivity.tsx

import React from 'react'
import { Clock, MapPin } from 'lucide-react'
import type { Observation } from '@/types'

interface RecentActivityProps {
  observations: Observation[]
}

const RecentActivity: React.FC<RecentActivityProps> = ({ observations }) => {
  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <div className="card p-6">
      <h3 className="text-lg font-bold text-white mb-4">Recent Activity</h3>
      <div className="space-y-3">
        {observations.slice(0, 5).map((obs) => (
          <div key={obs.id} className="flex items-center gap-3 p-3 rounded-lg bg-surface-light border border-border">
            <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <MapPin size={16} className="text-blue-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-white">{obs.plate_text || 'Unknown'}</p>
              <p className="text-xs text-muted">{obs.camera_id}</p>
            </div>
            <div className="text-xs text-muted flex items-center gap-1">
              <Clock size={12} />
              {formatDate(obs.timestamp)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default RecentActivity
