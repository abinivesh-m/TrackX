// frontend/src/components/common/StatCard.tsx
//
// Console data tile - flat panel, no motion, no gradient glow, no hover
// lift/scale. iconColor is still a Tailwind bg/text utility string passed
// by callers (kept for compatibility with existing call sites).

import React from 'react'
import { LucideIcon, TrendingUp, TrendingDown } from 'lucide-react'

interface StatCardProps {
  icon: LucideIcon
  label: string
  value: string
  iconColor: string
  hint?: string
  trend?: string
}

const StatCard: React.FC<StatCardProps> = ({ icon: Icon, label, value, iconColor, hint, trend }) => {
  const isPositive = trend?.startsWith('+')
  const isNegative = trend?.startsWith('-')

  return (
    <div className="card p-4 flex items-center gap-3.5">
      <div className={`w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0 ${iconColor}`}>
        <Icon size={19} />
      </div>

      <div className="flex-1 min-w-0">
        <p className="label-caps mb-1">{label}</p>
        <p className="text-2xl font-bold text-white font-data tabular-nums leading-none">{value}</p>

        {trend && (
          <div className="flex items-center gap-1 mt-1.5">
            {isPositive ? (
              <TrendingUp size={12} className="text-clear-400" />
            ) : isNegative ? (
              <TrendingDown size={12} className="text-critical-400" />
            ) : null}
            <span className={`text-[11px] font-semibold font-data ${isPositive ? 'text-clear-400' : isNegative ? 'text-critical-400' : 'text-muted'}`}>
              {trend}
            </span>
          </div>
        )}

        {hint && <p className="text-[11px] text-muted mt-1 truncate">{hint}</p>}
      </div>
    </div>
  )
}

export default StatCard
