// frontend/src/components/layout/Sidebar.tsx

import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Search,
  Camera,
  BarChart3,
  Bell,
  Settings,
  LogOut,
  X,
  Route,
  Map,
  Shield,
  Gauge,
  AlertOctagon,
  ScanLine
} from 'lucide-react'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

const navItems = [
  { path: '/dashboard', label: 'Operations', icon: LayoutDashboard, description: 'System overview' },
  { path: '/cameras', label: 'Camera Network', icon: Camera, description: 'Status & coverage' },
  { path: '/vehicles', label: 'Vehicle Intelligence', icon: Search, description: 'Search & track' },
  { path: '/trajectory', label: 'Trajectory Search', icon: Route, description: 'Route analysis' },
  { path: '/gis', label: 'GIS Map', icon: Map, description: 'City visualization' },
  { path: '/analytics', label: 'Traffic Analytics', icon: BarChart3, description: 'Congestion & patterns' },
  { path: '/congestion', label: 'Congestion', icon: Gauge, description: 'Bottleneck detection' },
  { path: '/route-anomaly', label: 'Route Anomalies', icon: AlertOctagon, description: 'Unusual movement' },
  { path: '/alerts', label: 'Alerts', icon: Bell, description: 'Security notifications' },
  { path: '/ai-processing', label: 'AI Processing', icon: ScanLine, description: 'Run detection on camera media' },
  { path: '/admin', label: 'System Admin', icon: Settings, adminOnly: true, description: 'Configuration' },
]

const Sidebar: React.FC<SidebarProps> = ({ open, onClose }) => {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const filteredNavItems = navItems.filter(item => 
    !item.adminOnly || user?.is_admin || user?.role === 'admin'
  )

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {open && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden"
            onClick={onClose}
          />
        )}
      </AnimatePresence>

      {/*
        Plain <aside>, not <motion.aside>, on purpose: Framer Motion's
        animate={{x: ...}} sets `transform` as an INLINE style, which beats
        every stylesheet rule - including the `lg:translate-x-0` media-query
        override below that's supposed to pin the sidebar open on desktop.
        With the inline style, the sidebar was permanently transformed off
        -screen (translateX(-256px)) at every viewport width, since
        `sidebarOpen` (Layout.tsx) defaults to false even on desktop and
        nothing there ever sets it true for wide screens - only the (now
        overridden) CSS media query was supposed to handle that case. Using
        plain Tailwind classes + a CSS transition here lets `lg:` actually
        win at desktop widths again.
      */}
      <aside
        className={`
          fixed z-50 lg:relative
          h-full w-64 flex-shrink-0
          bg-surface border-r border-border
          transition-transform duration-300 ease-in-out
          ${open ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Logo */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center justify-between">
            <motion.div 
              className="flex items-center gap-3"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
            >
              <motion.div 
                className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20"
                whileHover={{ scale: 1.05, rotate: 5 }}
                whileTap={{ scale: 0.95 }}
              >
                <span className="text-xl font-bold text-white">T</span>
              </motion.div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                  TrackX
                </h1>
                <p className="text-xs text-muted tracking-wider">CITY-WIDE VEHICLE INTELLIGENCE</p>
              </div>
            </motion.div>
            <motion.button 
              onClick={onClose}
              className="lg:hidden text-muted hover:text-white"
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
            >
              <X size={20} />
            </motion.button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {filteredNavItems.map((item, index) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={onClose}
              className="group relative block"
            >
              {({ isActive }) => (
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + index * 0.05 }}
                className={`
                  flex items-center gap-3 px-4 py-3 rounded-lg
                  transition-all duration-200
                  ${isActive 
                    ? 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 text-blue-400 border border-blue-500/30' 
                    : 'text-muted hover:text-white hover:bg-surface-light'}
                `}
                whileHover={{ scale: 1.02, x: 4 }}
                whileTap={{ scale: 0.98 }}
              >
                <item.icon size={20} className={`
                  transition-transform duration-200
                  ${'group-hover:scale-110'}
                `} />
                <div className="flex-1">
                  <span className="font-medium block">{item.label}</span>
                  <span className="text-xs opacity-60 block">{item.description}</span>
                </div>
                {isActive && (
                  <motion.div
                    className="absolute right-2 w-1.5 h-1.5 bg-blue-400 rounded-full"
                    animate={{
                      scale: [1, 1.2, 1],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                      repeatType: "loop"
                    }}
                  />
                )}
              </motion.div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Info */}
        <motion.div 
          className="p-4 border-t border-border"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="flex items-center gap-3 mb-4">
            <motion.div 
              className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg"
              whileHover={{ scale: 1.05, rotate: 5 }}
            >
              <span className="font-bold text-white">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </motion.div>
            <div>
              <p className="font-medium text-sm">{user?.username}</p>
              <p className="text-xs text-muted flex items-center gap-1">
                <Shield size={10} />
                {user?.role}
              </p>
            </div>
          </div>
          
          <motion.button 
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-2 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors w-full"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <LogOut size={18} />
            <span className="font-medium">Logout</span>
          </motion.button>
        </motion.div>
      </aside>
    </>
  )
}

export default Sidebar
