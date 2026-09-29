// frontend/src/pages/LoginPage.tsx
//
// Operator sign-in. Flat, no gradient logo/text/button - styled as an
// access panel to the ops console rather than a SaaS marketing login.

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-toastify'
import { useAuth } from '@/contexts/AuthContext'
import { Loader2, Lock, User, Eye, EyeOff } from 'lucide-react'

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!username || !password) {
      toast.error('Please enter username and password')
      return
    }

    setIsLoading(true)

    try {
      await login(username, password)
      toast.success('Login successful')
      navigate('/dashboard')
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        {/* Identity */}
        <div className="text-center mb-6">
          <div className="w-14 h-14 mx-auto rounded-sm bg-graphite-850 border border-signal-500/40 flex items-center justify-center mb-3">
            <span className="text-2xl font-bold text-signal-400 font-data">TX</span>
          </div>
          <h1 className="text-xl font-bold text-white tracking-tight">TrackX</h1>
          <p className="text-xs text-muted font-data tracking-widest mt-1">ANPR OPERATIONS CONSOLE</p>
        </div>

        {/* Access panel */}
        <div className="card p-6">
          <div className="label-caps mb-4 flex items-center justify-between">
            <span>Operator Sign-In</span>
            <span className="text-clear-400">SESSION SECURE</span>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Operator ID"
                  className="input w-full pl-9"
                  autoFocus
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-muted mb-1.5">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={16} />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input w-full pl-9 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-white"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="animate-spin" size={16} />
                  Authenticating...
                </>
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-5 pt-4 border-t border-border text-center">
            <p className="text-[11px] text-muted font-data">
              DEMO ACCESS · admin@trackx.com / admin123
            </p>
          </div>
        </div>

        <p className="text-center text-[11px] text-muted mt-6 font-data">
          TRACKX · SIH 26127 · BHARAT ELECTRONICS LIMITED
        </p>
      </div>
    </div>
  )
}

export default LoginPage
