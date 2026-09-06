// frontend/src/components/common/StatCard.tsx

import React from 'react'
import { LucideIcon } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: string
  iconColor: string
  hint?: string
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, label, value, iconColor, hint }) => {
  return (
    <div className="card p-6 flex items-center gap-4">
      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${iconColor}`}>
        <Icon size={24} />
      </div>
      <div>
        <p className="text-xs text-muted uppercase tracking-wider font-semibold">{label}</p>
        <p className="text-2xl font-bold text-white mt-1">{value}</p>
        {hint && <p className="text-xs text-muted mt-1">{hint}</p>}
      </div>
    </div>
  )
}

export default StatCard
