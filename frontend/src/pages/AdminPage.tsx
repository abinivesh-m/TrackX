// frontend/src/pages/AdminPage.tsx

import React, { useState, useEffect } from 'react'
import { api } from '@/services/api'
import { useAuth } from '@/contexts/AuthContext'
import { Users, Activity, Shield, Database, Server } from 'lucide-react'
import type { User } from '@/types'

const AdminPage: React.FC = () => {
  const { user } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('users')

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const data = await api.getUsers()
        setUsers(data)
      } catch (error) {
        console.error('Failed to fetch users:', error)
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchUsers()
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Server size={20} className="text-blue-400" />
                  <span className="font-medium text-white">API Server</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
                  <span className="text-sm text-green-400">Running</span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Database size={20} className="text-green-400" />
                  <span className="font-medium text-white">Database</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
                  <span className="text-sm text-green-400">Connected</span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Activity size={20} className="text-purple-400" />
                  <span className="font-medium text-white">AI Processing</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-blue-500 rounded-full pulse" />
                  <span className="text-sm text-blue-400">Active</span>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center gap-3 mb-2">
                  <Shield size={20} className="text-yellow-400" />
                  <span className="font-medium text-white">Security</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
                  <span className="text-sm text-green-400">Enabled</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Security Settings</h3>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Two-Factor Authentication</p>
                    <p className="text-xs text-muted">Enable 2FA for enhanced security</p>
                  </div>
                  <button className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-sm hover:bg-blue-500/30">
                    Configure
                  </button>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Session Timeout</p>
                    <p className="text-xs text-muted">Current: 30 minutes</p>
                  </div>
                  <button className="px-4 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-sm hover:bg-blue-500/30">
                    Update
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'database' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Database Management</h3>
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Backup Database</p>
                    <p className="text-xs text-muted">Create a full backup of the database</p>
                  </div>
                  <button className="px-4 py-2 rounded-lg bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30">
                    Backup
                  </button>
                </div>
              </div>
              <div className="p-4 rounded-lg bg-surface-light border border-border">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Clear Old Observations</p>
                    <p className="text-xs text-muted">Remove observations older than 30 days</p>
                  </div>
                  <button className="px-4 py-2 rounded-lg bg-red-500/20 text-red-400 text-sm hover:bg-red-500/30">
                    Clear
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div>
            <h3 className="text-lg font-bold text-white mb-4">Audit Logs</h3>
            <div className="space-y-2">
              {[
                { action: 'User login', user: 'admin', time: '2 minutes ago' },
                { action: 'Alert resolved', user: 'operator', time: '15 minutes ago' },
                { action: 'Camera added', user: 'admin', time: '1 hour ago' },
                { action: 'System health check', user: 'system', time: '2 hours ago' },
              ].map((log, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-surface-light border border-border">
                  <div className="flex items-center gap-3">
                    <Activity size={16} className="text-muted" />
                    <div>
                      <p className="text-sm text-white">{log.action}</p>
                      <p className="text-xs text-muted">by {log.user}</p>
                    </div>
                  </div>
                  <span className="text-xs text-muted">{log.time}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default AdminPage
