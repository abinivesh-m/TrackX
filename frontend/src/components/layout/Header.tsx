// frontend/src/components/layout/Header.tsx

import React, { useState, useEffect } from 'react'
import { Menu, Moon, Sun, Bell, Search, Clock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '@/services/api'
import type { Alert } from '@/types'

interface HeaderProps {
  onMenuClick: () => void
  theme: 'dark' | 'light'
  onThemeToggle: () => void
}

function timeAgo(ts: string): string {
  const ms = Date.now() - new Date(ts).getTime()
  const mins = Math.floor(ms / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function severityColor(severity: string) {
  if (severity === 'HIGH') return 'bg-red-500'
  if (severity === 'MEDIUM') return 'bg-yellow-500'
  return 'bg-blue-500'
}

const Header: React.FC<HeaderProps> = ({ onMenuClick, theme, onThemeToggle }) => {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [currentTime, setCurrentTime] = useState(new Date())
  const [showNotifications, setShowNotifications] = useState(false)
  // Real open alerts from GET /alerts and GET /alerts/stats - the same data
  // source the Overview page's "Active Alerts" KPI and the Alert Center
  // page use, so this bell's count is never a second, separately-fabricated
  // number (Phase "FINAL WINNING UI PASS" requirement: "Notification bell
  // must use the same alert data. No duplicate unread counts."). The badge
  // count comes from /alerts/stats' real open_alerts total, NOT from
  // counting the 5-item preview list below - that list is capped to 5 for
  // the dropdown, so using its .length as the badge would silently show
  // "5" forever once there are 5 or more open alerts (the same undercount
  // bug just fixed on the Overview page's KPI). Fetched once on mount and
  // refreshed on open - matching this app's existing fetch-once/on-demand
  // pattern (nothing in TrackX auto-polls in the background; see Phase
  // 12's honesty-audit notes on Sidebar/Analytics/GIS).
  const [openAlerts, setOpenAlerts] = useState<Alert[]>([])
  const [openAlertCount, setOpenAlertCount] = useState(0)
  const [alertsError, setAlertsError] = useState(false)

  const loadAlerts = () => {
    Promise.all([
      api.getAlerts({ status: 'OPEN', limit: 5 }),
      api.getAlertStats(),
    ])
      .then(([recent, stats]) => {
        setOpenAlerts(recent)
        setOpenAlertCount(stats.open_alerts)
        setAlertsError(false)
      })
      .catch(() => setAlertsError(true))
  }

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    loadAlerts()
    return () => clearInterval(timer)
  }, [])

  const handleBellClick = () => {
    setShowNotifications((v) => !v)
    loadAlerts()
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/vehicles?plate=${encodeURIComponent(searchQuery)}`)
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      second: '2-digit'
    })
  }

  return (
    <motion.header 
      className="h-16 border-b border-border flex items-center justify-between px-6 bg-surface/95 backdrop-blur-sm sticky top-0 z-30"
      initial={{ y: -100 }}
      animate={{ y: 0 }}
      transition={{ duration: 0.5, type: "spring" }}
    >
      <div className="flex items-center gap-4">
        <motion.button 
          onClick={onMenuClick}
          className="lg:hidden text-muted hover:text-white p-2 rounded-lg hover:bg-surface-light transition-colors"
          whileHover={{ scale: 1.1, rotate: 180 }}
          whileTap={{ scale: 0.95 }}
          transition={{ duration: 0.3 }}
        >
          <Menu size={24} />
        </motion.button>
        
        {/* Global Search */}
        <form onSubmit={handleSearch} className="hidden md:flex items-center">
          <div className="relative group">
            <motion.div 
              className="absolute left-3 top-1/2 -translate-y-1/2"
              animate={{ 
                scale: [1, 1.1, 1],
                color: ['#94a3b8', '#60a5fa', '#94a3b8']
              }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Search className="text-muted group-focus-within:text-blue-400 transition-colors" size={16} />
            </motion.div>
            <motion.input
              type="text"
              placeholder="Search vehicle plate..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2.5 rounded-xl bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-sm w-72 transition-all duration-300 focus:w-80 focus:ring-2 focus:ring-blue-500/20 backdrop-blur-sm"
              initial={{ opacity: 0.8 }}
              animate={{ opacity: 1 }}
              whileFocus={{ scale: 1.02, boxShadow: "0 0 0 3px rgba(59, 130, 246, 0.15)" }}
              transition={{ duration: 0.3 }}
            />
          </div>
        </form>
      </div>

      <div className="flex items-center gap-3">
        {/* Current Time */}
        <motion.div 
          className="hidden md:flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-light border border-border hover:border-blue-500/30 transition-colors cursor-pointer"
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
        >
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
          >
            <Clock size={16} className="text-blue-400" />
          </motion.div>
          <span className="text-xs font-mono text-muted font-semibold">{formatTime(currentTime)}</span>
        </motion.div>

        {/* Theme Toggle */}
        <motion.button 
          onClick={onThemeToggle}
          className="p-2.5 rounded-xl text-muted hover:text-white hover:bg-surface-light transition-colors border border-transparent hover:border-border"
          whileHover={{ scale: 1.1, rotate: 180 }}
          whileTap={{ scale: 0.95 }}
          transition={{ duration: 0.4, type: "spring" }}
        >
          <AnimatePresence mode="wait">
            {theme === 'dark' ? (
              <motion.div
                key="sun"
                initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.3, type: "spring" }}
              >
                <Sun size={20} />
              </motion.div>
            ) : (
              <motion.div
                key="moon"
                initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
                animate={{ rotate: 0, opacity: 1, scale: 1 }}
                exit={{ rotate: 90, opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.3, type: "spring" }}
              >
                <Moon size={20} />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.button>

        {/* Notifications - real open alerts from GET /alerts, aria-labeled
            with the real count for screen readers/tooltips rather than an
            icon-only control. */}
        <div className="relative">
          <motion.button
            className="relative p-2.5 rounded-xl text-muted hover:text-white hover:bg-surface-light transition-colors border border-transparent hover:border-border"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleBellClick}
            aria-label={`Notifications: ${openAlertCount} open alert${openAlertCount === 1 ? '' : 's'}`}
            title={`${openAlertCount} open alert${openAlertCount === 1 ? '' : 's'}`}
          >
            <Bell size={20} />
            {openAlertCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 flex items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white leading-none">
                {openAlertCount > 9 ? '9+' : openAlertCount}
              </span>
            )}
          </motion.button>

          <AnimatePresence>
            {showNotifications && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.2, type: "spring" }}
                className="absolute right-0 top-12 w-80 bg-surface border border-border rounded-xl shadow-2xl overflow-hidden z-50 backdrop-blur-xl"
              >
                <div className="p-4 border-b border-border bg-gradient-to-r from-blue-500/10 to-purple-500/10 flex items-center justify-between">
                  <h3 className="font-semibold text-sm text-white">Recent Alerts</h3>
                  {openAlertCount > 0 && (
                    <span className="text-xs text-muted">{openAlertCount} open</span>
                  )}
                </div>
                <div className="max-h-72 overflow-y-auto">
                  {alertsError ? (
                    <div className="px-4 py-8 text-center text-xs text-muted">
                      TrackX services are temporarily unavailable.
                    </div>
                  ) : openAlertCount === 0 ? (
                    <div className="px-4 py-8 text-center text-xs text-muted">
                      No open alerts right now.
                    </div>
                  ) : (
                    openAlerts.map((alert) => (
                      <button
                        key={alert.id}
                        onClick={() => { setShowNotifications(false); navigate('/alerts') }}
                        className="w-full text-left px-4 py-3 border-b border-border last:border-b-0 hover:bg-surface-light transition-colors flex items-start gap-3"
                      >
                        <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${severityColor(alert.severity)}`} />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-semibold text-white truncate">
                            {alert.alert_type.replace(/_/g, ' ')}
                          </p>
                          <p className="text-xs text-muted truncate">
                            {alert.plate_text || alert.camera_id || 'System-wide'}
                          </p>
                          <p className="text-[10px] text-muted/70 mt-0.5">{timeAgo(alert.timestamp)}</p>
                        </div>
                      </button>
                    ))
                  )}
                </div>
                <button
                  onClick={() => { setShowNotifications(false); navigate('/alerts') }}
                  className="w-full text-center text-xs text-blue-400 hover:text-blue-300 py-2.5 border-t border-border transition-colors"
                >
                  View all alerts →
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Status Indicator */}
        <motion.div 
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-light border border-border hover:border-green-500/30 transition-colors cursor-pointer"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, type: "spring" }}
          whileHover={{ scale: 1.05, y: -2 }}
          whileTap={{ scale: 0.95 }}
        >
          <div className="relative">
            <span className="w-2.5 h-2.5 bg-green-500 rounded-full" />
            <motion.span 
              className="absolute inset-0 w-2.5 h-2.5 bg-green-500 rounded-full"
              animate={{
                scale: [1, 1.5, 1],
                opacity: [1, 0.5, 1]
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                repeatType: "loop"
              }}
            />
          </div>
          <span className="text-xs font-bold text-green-400 tracking-wide">TRACKX</span>
        </motion.div>
      </div>
    </motion.header>
  )
}

export default Header
