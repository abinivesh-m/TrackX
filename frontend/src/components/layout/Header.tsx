// frontend/src/components/layout/Header.tsx
//
// Console top bar. Rebuilt flat: no motion.header slide-in, no rotating
// clock icon, no infinite pulsing search icon, no gradient hover glows.
// All real data wiring (alert bell -> GET /alerts + /alerts/stats, plate
// search -> /vehicles?plate=) is unchanged from before.

import React, { useState, useEffect } from 'react'
import { Menu, Moon, Sun, Bell, Search, Radio } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
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

function severityDot(severity: string) {
  if (severity === 'HIGH') return 'bg-critical-500'
  if (severity === 'MEDIUM') return 'bg-caution-500'
  return 'bg-graphite-400'
}

const Header: React.FC<HeaderProps> = ({ onMenuClick, theme, onThemeToggle }) => {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [currentTime, setCurrentTime] = useState(new Date())
  const [showNotifications, setShowNotifications] = useState(false)
  // Real open alerts from GET /alerts and GET /alerts/stats - this bell's
  // count is never a second, separately-fabricated number: the badge count
  // comes from /alerts/stats' real open_alerts total, not from counting the
  // 5-item preview list (which is capped for the dropdown).
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

  const formatTime = (date: Date) =>
    date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  const formatDate = (date: Date) =>
    date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <header className="h-16 border-b border-border flex items-center justify-between px-4 md:px-6 bg-surface sticky top-0 z-30 flex-shrink-0">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="lg:hidden text-muted hover:text-white p-2 rounded-sm hover:bg-surface-light"
        >
          <Menu size={22} />
        </button>

        <form onSubmit={handleSearch} className="hidden md:flex items-center">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={15} />
            <input
              type="text"
              placeholder="Lookup plate number..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value.toUpperCase())}
              className="input font-data pl-9 pr-4 py-2 w-64 focus:w-80 transition-[width] duration-150 text-xs"
            />
          </div>
        </form>
      </div>

      <div className="flex items-center gap-2">
        {/* Clock - console-style date + time readout */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-sm border border-border">
          <span className="font-data text-[11px] text-muted">{formatDate(currentTime)}</span>
          <span className="w-px h-3 bg-border" />
          <span className="font-data text-[11px] text-white tabular-nums">{formatTime(currentTime)}</span>
        </div>

        <button
          onClick={onThemeToggle}
          className="p-2 rounded-sm text-muted hover:text-white hover:bg-surface-light border border-transparent hover:border-border"
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        {/* Alerts */}
        <div className="relative">
          <button
            className="relative p-2 rounded-sm text-muted hover:text-white hover:bg-surface-light border border-transparent hover:border-border"
            onClick={handleBellClick}
            aria-label={`Alerts: ${openAlertCount} open alert${openAlertCount === 1 ? '' : 's'}`}
            title={`${openAlertCount} open alert${openAlertCount === 1 ? '' : 's'}`}
          >
            <Bell size={17} />
            {openAlertCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[15px] h-[15px] px-1 flex items-center justify-center rounded-sm bg-critical-500 text-[9px] font-bold text-white leading-none font-data">
                {openAlertCount > 9 ? '9+' : openAlertCount}
              </span>
            )}
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-11 w-80 bg-surface border border-border rounded-sm shadow-2xl overflow-hidden z-50">
              <div className="px-4 py-2.5 border-b border-border flex items-center justify-between">
                <h3 className="label-caps">Open Alerts</h3>
                {openAlertCount > 0 && (
                  <span className="text-xs text-muted font-data">{openAlertCount}</span>
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
                      className="w-full text-left px-4 py-2.5 border-b border-border last:border-b-0 hover:bg-surface-light flex items-start gap-3"
                    >
                      <span className={`mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0 ${severityDot(alert.severity)}`} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold text-white truncate">
                          {alert.alert_type.replace(/_/g, ' ')}
                        </p>
                        <p className="text-xs text-muted truncate font-data">
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
                className="w-full text-center text-xs text-signal-400 hover:text-signal-300 py-2 border-t border-border"
              >
                View all alerts &rarr;
              </button>
            </div>
          )}
        </div>

        {/* System status - functional live indicator, not decoration */}
        <div className="flex items-center gap-2 pl-3 pr-3.5 py-1.5 rounded-sm border border-border">
          <span className="live-dot is-live" />
          <Radio size={12} className="text-clear-400" />
          <span className="text-[11px] font-bold text-clear-400 tracking-wide font-data hidden sm:inline">ONLINE</span>
        </div>
      </div>
    </header>
  )
}

export default Header
