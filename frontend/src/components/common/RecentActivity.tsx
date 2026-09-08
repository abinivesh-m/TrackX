// frontend/src/components/common/RecentActivity.tsx

import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, MapPin, Activity } from 'lucide-react'
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
    <motion.div 
      className="card p-6"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-white flex items-center gap-2">
          <Activity className="text-blue-400" size={20} />
          Recent Activity
        </h3>
        <motion.div 
          className="w-2 h-2 bg-green-500 rounded-full"
          animate={{
            scale: [1, 1.3, 1],
            opacity: [1, 0.7, 1]
          }}
          transition={{
            duration: 2,
            repeat: Infinity
          }}
        />
      </div>
      
      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {observations.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center py-8 text-muted"
            >
              <Activity size={32} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">No recent activity</p>
            </motion.div>
          ) : (
            observations.slice(0, 5).map((obs, index) => (
              <motion.div
                key={obs.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ delay: index * 0.1, duration: 0.3 }}
                className="group flex items-center gap-3 p-3 rounded-xl bg-surface-light border border-border hover:border-blue-500/30 hover:bg-surface transition-all cursor-pointer"
                whileHover={{ scale: 1.02, x: 4 }}
              >
                <motion.div 
                  className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center border border-blue-500/20"
                  whileHover={{ scale: 1.1, rotate: 5 }}
                  transition={{ duration: 0.2 }}
                >
                  <MapPin size={18} className="text-blue-400" />
                </motion.div>
                
                <div className="flex-1 min-w-0">
                  <motion.p 
                    className="text-sm font-semibold text-white truncate"
                    whileHover={{ color: '#60a5fa' }}
                  >
                    {obs.plate_text || 'Unknown'}
                  </motion.p>
                  <p className="text-xs text-muted mt-0.5">{obs.camera_id}</p>
                </div>
                
                <div className="text-xs text-muted flex items-center gap-1.5 bg-surface px-2 py-1 rounded-lg">
                  <Clock size={12} className="text-blue-400" />
                  {formatDate(obs.timestamp)}
                </div>
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  )
}

export default RecentActivity
