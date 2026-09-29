// frontend/src/components/layout/Sidebar.tsx
//
// Console navigation rail. Rebuilt away from the generic "AI dashboard"
// sidebar pattern: no gradient logo mark, no per-item stagger animation, no
// pulsing active-state dot, no hover scale/rotate on icons. Active route is
// marked the way an ops console marks a selected panel - a left accent bar
// and a flat tint, nothing that moves.
//
// Plain <aside>, not <motion.aside>: Framer Motion's animate={{x: ...}} sets
// `transform` as an INLINE style, which beats every stylesheet rule -
// including the `lg:translate-x-0` media-query override below that pins the
// sidebar open on desktop. Keep this plain-CSS-transition approach; do not
// reintroduce motion.aside here.

import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import {
  LayoutGrid,
  Search,
  Video,
  BarChart3,
  Bell,
  Settings,
  LogOut,
  X,
  Route,
  Map,
  ShieldAlert,
  Gauge,
  AlertOctagon,
  ScanEye,
  Camera as CameraIcon,
  LucideIcon
} from 'lucide-react'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

// Grouped by pipeline stage (Camera -> Detection -> Matching -> Journey ->
// Map -> Intelligence -> Alerts -> Admin) rather than an arbitrary flat
// list, so the nav itself communicates how the system works.
const navGroups: {
  label: string
  items: { path: string; label: string; icon: LucideIcon; adminOnly?: boolean }[]
}[] = [
  {
    label: 'Console',
    items: [
      { path: '/dashboard', label: 'Operations', icon: LayoutGrid },
    ],
  },
  {
    label: 'Capture & Recognition',
    items: [
      { path: '/cameras', label: 'Camera Network', icon: Video },
      { path: '/ai-processing', label: 'Detection Pipeline', icon: ScanEye },
      { path: '/live-webcam', label: 'Live Webcam Demo', icon: CameraIcon },
      { path: '/vehicles', label: 'Vehicle Search', icon: Search },
    ],
  },
  {
    label: 'Journey & Map',
    items: [
      { path: '/trajectory', label: 'Trajectory Search', icon: Route },
      { path: '/gis', label: 'GIS Map', icon: Map },
    ],
  },
  {
    label: 'Traffic Intelligence',
    items: [
      { path: '/analytics', label: 'Traffic Analytics', icon: BarChart3 },
      { path: '/congestion', label: 'Congestion', icon: Gauge },
      { path: '/route-anomaly', label: 'Route Anomalies', icon: AlertOctagon },
    ],
  },
  {
    label: 'Enforcement',
    items: [
      { path: '/alerts', label: 'Alerts', icon: Bell },
    ],
  },
  {
    label: 'System',
    items: [
      { path: '/admin', label: 'System Admin', icon: Settings, adminOnly: true },
    ],
  },
]

const Sidebar: React.FC<SidebarProps> = ({ open, onClose }) => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const isAdmin = user?.is_admin || user?.role === 'admin'

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`
          fixed z-50 lg:relative
          h-full w-64 flex-shrink-0
          bg-surface border-r border-border
          flex flex-col
          transition-transform duration-200 ease-out
          ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Identity block */}
        <div className="px-4 h-16 border-b border-border flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-sm bg-graphite-750 border border-signal-500/40 flex items-center justify-center flex-shrink-0">
              <span className="text-signal-400 font-data font-bold text-sm">TX</span>
            </div>
            <div className="leading-tight">
              <h1 className="text-sm font-bold text-white tracking-tight">TrackX</h1>
              <p className="text-[10px] text-muted tracking-widest font-data">ANPR OPS CONSOLE</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden text-muted hover:text-white p-1"
          >
            <X size={18} />
          </button>
        </div>

        {/* Navigation, grouped by pipeline stage */}
        <nav className="flex-1 overflow-y-auto py-3">
          {navGroups.map((group) => {
            const visibleItems = group.items.filter((item) => !item.adminOnly || isAdmin)
            if (visibleItems.length === 0) return null
            return (
              <div key={group.label} className="mb-4">
                <div className="px-4 mb-1.5 label-caps">{group.label}</div>
                <div className="px-2 space-y-0.5">
                  {visibleItems.map((item) => (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={onClose}
                      className={({ isActive }) => `
                        flex items-center gap-2.5 pl-3 pr-3 py-2 rounded-sm text-[13px] font-medium
                        border-l-2 transition-colors duration-100
                        ${isActive
                          ? 'bg-signal-500/[0.08] border-signal-500 text-white'
                          : 'border-transparent text-muted hover:text-white hover:bg-surface-light'}
                      `}
                    >
                      <item.icon size={16} className="flex-shrink-0" />
                      <span className="truncate">{item.label}</span>
                    </NavLink>
                  ))}
                </div>
              </div>
            )
          })}
        </nav>

        {/* Operator identity + logout */}
        <div className="p-3 border-t border-border flex-shrink-0">
          <div className="flex items-center gap-2.5 px-2 py-2 mb-1">
            <div className="w-7 h-7 rounded-sm bg-graphite-750 border border-border flex items-center justify-center flex-shrink-0">
              <span className="font-data text-xs font-bold text-muted">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-white truncate">{user?.username}</p>
              <p className="text-[10px] text-muted flex items-center gap-1">
                <ShieldAlert size={9} />
                {user?.role}
              </p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 px-2 py-1.5 rounded-sm text-critical-400 hover:bg-critical-500/10 transition-colors w-full text-xs font-semibold"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>
    </>
  )
}

export default Sidebar
