// frontend/src/pages/NotFoundPage.tsx

import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Home, ArrowLeft } from 'lucide-react'

const NotFoundPage: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <h1 className="text-9xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
          404
        </h1>
        <h2 className="text-2xl font-bold text-white mt-4">Page Not Found</h2>
        <p className="text-muted mt-2">The page you're looking for doesn't exist.</p>
        
        <div className="flex gap-4 justify-center mt-8">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 px-6 py-3 rounded-lg bg-surface-light border border-border text-white hover:bg-surface-light/50 transition-colors"
          >
            <ArrowLeft size={20} />
            Go Back
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white font-bold hover:opacity-90 transition-opacity"
          >
            <Home size={20} />
            Dashboard
          </button>
        </div>
      </div>
    </div>
  )
}

export default NotFoundPage
