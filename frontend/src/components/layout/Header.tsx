// frontend/src/components/layout/Header.tsx

import React from 'react'
import { Menu, Moon, Sun, Bell, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

interface HeaderProps {
  onMenuClick: () => void
  theme: 'dark' | 'light'
  onThemeToggle: () => void
}

const Header: React.FC<HeaderProps> = ({ onMenuClick, theme, onThemeToggle }) => {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      navigate(`/vehicles?plate=${encodeURIComponent(searchQuery)}`)
    }
  }

  return (
    <header className="h-16 border-b border-border flex items-center justify-between px-6 bg-surface">
      <div className="flex items-center gap-4">
        <button 
          onClick={onMenuClick}
          className="lg:hidden text-muted hover:text-white"
        >
          <Menu size={24} />
        </button>
        
        {/* Global Search */}
        <form onSubmit={handleSearch} className="hidden md:flex items-center">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
            <input
              type="text"
              placeholder="Search vehicle plate..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-sm w-72"
            />
          </div>
        </form>
      </div>

      <div className="flex items-center gap-4">
        {/* Theme Toggle */}
        <button 
          onClick={onThemeToggle}
          className="p-2 rounded-lg text-muted hover:text-white hover:bg-surface-light transition-colors"
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
        </button>

        {/* Notifications */}
        <button className="relative p-2 rounded-lg text-muted hover:text-white hover:bg-surface-light transition-colors">
          <Bell size={20} />
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full pulse" />
        </button>

        {/* Status Indicator */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-surface-light border border-border">
          <span className="w-2 h-2 bg-green-500 rounded-full pulse" />
          <span className="text-xs font-medium text-green-400">SYSTEM ONLINE</span>
        </div>
      </div>
    </header>
  )
}

export default Header
