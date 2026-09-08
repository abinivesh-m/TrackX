// frontend/src/components/common/StatCard.tsx

import React from 'react'
import { motion } from 'framer-motion'
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
    <motion.div 
      className="card p-6 flex items-center gap-4 relative overflow-hidden group"
      whileHover={{ scale: 1.03, y: -4 }}
      transition={{ duration: 0.3, type: "spring", stiffness: 300 }}
    >
      {/* Animated background gradient */}
      <motion.div 
        className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100"
        transition={{ duration: 0.3 }}
      />
      
      {/* Subtle pulse effect */}
      <motion.div 
        className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5"
        animate={{
          opacity: [0.3, 0.5, 0.3],
        }}
        transition={{
          duration: 3,
          repeat: Infinity,
          repeatType: "reverse"
        }}
      />
      
      {/* Icon container with enhanced effects */}
      <motion.div 
        className={`w-14 h-14 rounded-xl flex items-center justify-center ${iconColor} relative z-10`}
        whileHover={{ rotate: 8, scale: 1.15 }}
        transition={{ duration: 0.3, type: "spring" }}
      >
        <motion.div
          animate={{
            scale: [1, 1.05, 1],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatType: "reverse"
          }}
        >
          <Icon size={26} />
        </motion.div>
        {/* Glow effect */}
        <motion.div 
          className={`absolute inset-0 rounded-xl ${iconColor} blur-xl opacity-50`}
          animate={{
            opacity: [0.3, 0.6, 0.3],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatType: "reverse"
          }}
        />
      </motion.div>
      
      <div className="relative z-10 flex-1">
        <p className="text-xs text-muted uppercase tracking-widest font-semibold mb-1">{label}</p>
        <motion.p 
          className="text-3xl font-bold text-white bg-gradient-to-r from-white to-gray-200 bg-clip-text text-transparent"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, type: "spring", stiffness: 200 }}
        >
          {value}
        </motion.p>
        
        {trend && (
          <motion.div 
            className="flex items-center gap-1.5 mt-2"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
          >
            {isPositive ? (
              <motion.div
                animate={{ y: [0, -3, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <TrendingUp size={14} className="text-green-400" />
              </motion.div>
            ) : isNegative ? (
              <motion.div
                animate={{ y: [0, 3, 0] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <TrendingDown size={14} className="text-red-400" />
              </motion.div>
            ) : null}
            <span className={`text-xs font-semibold ${isPositive ? 'text-green-400' : isNegative ? 'text-red-400' : 'text-muted'}`}>
              {trend}
            </span>
          </motion.div>
        )}
        
        {hint && <p className="text-xs text-muted mt-1.5 opacity-70">{hint}</p>}
      </div>
    </motion.div>
  )
}

export default StatCard
