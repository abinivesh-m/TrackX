import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import VehicleTracking from './pages/VehicleTracking'
import Analytics from './pages/Analytics'
import Alerts from './pages/Alerts'
import Navigation from './components/Navigation'
import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'https://trackx-2.onrender.com'

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

function App() {
  const [isHealthy, setIsHealthy] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [])

  const checkHealth = async () => {
    try {
      const response = await apiClient.get('/health')
      setIsHealthy(response.data.status === 'healthy')
      setLoading(false)
    } catch (error) {
      console.error('Health check failed:', error)
      setIsHealthy(false)
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-white text-lg">Connecting to TrackX...</p>
        </div>
      </div>
    )
  }

  if (!isHealthy) {
    return (
      <div className="w-full h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <p className="text-white text-lg mb-2">Service Unavailable</p>
          <p className="text-gray-400">Cannot connect to TrackX backend</p>
          <p className="text-gray-500 text-sm mt-4">API URL: {API_URL}</p>
        </div>
      </div>
    )
  }

  return (
    <Router>
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <Navigation />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/tracking" element={<VehicleTracking />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/alerts" element={<Alerts />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App
