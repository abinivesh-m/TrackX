// frontend/src/pages/AdminPage.tsx
//
// The System tab reads GET /health (the same real database/model checks
// Phase 8 wired the Operations Center dashboard to) instead of hardcoded
// "Running"/"Connected"/"Active" badges. The Security/Database tabs' controls
// have no backend behind them in this build, so they're shown as disabled
// with an honest label rather than as working buttons that do nothing when
// clicked. Audit Logs previously showed four fabricated example entries
// ("User login... 2 minutes ago") on every load - there is no audit-log
// store in this codebase, so that's now stated plainly instead.

import React, { useState, useEffect } from 'react'
import { toast } from 'react-toastify'
import { api } from '@/services/api'
import { useAuth } from '@/contexts/AuthContext'
import { Users, Activity, Shield, Database, Server, WifiOff } from 'lucide-react'
import type { User } from '@/types'

const AdminPage: React.FC = () => {
  const { user } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [health, setHealth] = useState<any>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('users')

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [usersData, healthData] = await Promise.all([
          api.getUsers(),
          api.getHealth().catch(() => null),
        ])
        setUsers(usersData)
        setHealth(healthData)
        setLoadError(null)
      } catch (error) {
        console.error('Failed to fetch admin data:', error)
        setLoadError('Could not reach the TrackX API.')
        toast.error('Failed to load admin data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  const tabs = [
    { id: 'users', label: 'Users', icon: Users },
    { id: 'system', label: 'System', icon: Server },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'database', label: 'Database', icon: Database },
    { id: 'logs', label: 'Audit Logs', icon: Activity },
  ]

  if (isLoading) {
    return <div className="flex justify-center items-center h-full">Loading...</div>
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center gap-2 text-red-300">
        <WifiOff size={32} />
        <p className="text-lg font-medium">{loadError}</p>
        <p className="text-sm text-muted">Admin console could not be loaded. Try refreshing the page.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Admin Console</h1>
        <span className="text-sm text-muted">Logged in as: {user?.username}</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-muted hover:text-white'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="card p-6">
        {activeTab === 'users' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">User Management</h3>
            <div className="space-y-3">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between p-4 rounded-lg bg-surface-light border border-border">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
                      <span className="font-bold text-white">{u.username[0].toUpperCase()}</span>
                    </div>
                    <div>
                      <p className="font-medium text-white">{u.username}</p>
                      <p className="text-xs text-muted">{u.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      u.role === 'admin' ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {u.role}
                    </span>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      u.is_active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'system' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">System Health</h3>
            {!health && (
              <p className="text-sm text-amber-300 mb-4">
                Could not reach GET /health - status below may be stale or unavailable.
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Server size={20} className="text-blue-400" />
                  <span className="font-medium text-white">API Server</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${health ? 'bg-green-500 pulse' : 'bg-red-500'}`} />
                  <span className={`text-sm ${health ? 'text-green-400' : 'text-red-400'}`}>
                    {health ? 'Reachable' : 'Unreachable'}
                  </span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Database size={20} className="text-green-400" />
                  <span className="font-medium text-white">Database</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${health?.database === 'healthy' ? 'bg-green-500 pulse' : 'bg-red-500'}`} />
                  <span className={`text-sm ${health?.database === 'healthy' ? 'text-green-400' : 'text-red-400'}`}>
                    {health?.database ? health.database : 'Unknown'}
                    {typeof health?.database_details?.observation_count === 'number'
                      ? ` (${health.database_details.observation_count} observations)`
                      : ''}
                  </span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Activity size={20} className="text-purple-400" />
                  <span className="font-medium text-white">AI / OCR Engine</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${health?.ai_engine === 'healthy' ? 'bg-blue-500 pulse' : 'bg-red-500'}`} />
                  <span className={`text-sm ${health?.ai_engine === 'healthy' ? 'text-blue-400' : 'text-red-400'}`}>
                    {health?.ai_engine || 'Unknown'}{health?.ocr_engine ? ` - ${health.ocr_engine}` : ''}
                  </span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Shield size={20} className="text-yellow-400" />
                  <span className="font-medium text-white">Auth</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
                  <span className="text-sm text-green-400">JWT-protected (you are signed in)</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Security Settings</h3>
            <p className="text-xs text-muted mb-4">
              Not configurable from this build - these controls are not wired to a backend yet.
            </p>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border opacity-60">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Two-Factor Authentication</p>
                    <p className="text-xs text-muted">Not implemented in this build</p>
                  </div>
                  <button disabled className="px-4 py-2 rounded-lg bg-surface text-muted text-sm cursor-not-allowed">
                    Unavailable
                  </button>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border opacity-60">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Session Timeout</p>
                    <p className="text-xs text-muted">Not configurable in this build</p>
                  </div>
                  <button disabled className="px-4 py-2 rounded-lg bg-surface text-muted text-sm cursor-not-allowed">
                    Unavailable
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'database' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Database Management</h3>
            <p className="text-xs text-muted mb-4">
              Not available from this build - no backup/purge endpoint exists yet. Use the sqlite
              file directly if you need to back up or prune data.
            </p>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border opacity-60">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Backup Database</p>
                    <p className="text-xs text-muted">Not implemented in this build</p>
                  </div>
                  <button disabled className="px-4 py-2 rounded-lg bg-surface text-muted text-sm cursor-not-allowed">
                    Unavailable
                  </button>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border opacity-60">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Clear Old Observations</p>
                    <p className="text-xs text-muted">Not implemented in this build</p>
                  </div>
                  <button disabled className="px-4 py-2 rounded-lg bg-surface text-muted text-sm cursor-not-allowed">
                    Unavailable
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Audit Logs</h3>
            <div className="p-4 rounded-lg bg-surface-light border border-border text-sm text-muted">
              Audit logging is not implemented in this build - there is no persisted record of
              admin/operator actions to show here. (Previous versions of this page showed four
              fabricated example entries at this location; they were not real activity.)
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AdminPage
