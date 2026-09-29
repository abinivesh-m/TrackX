// frontend/src/pages/NotFoundPage.tsx

import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Home, ArrowLeft } from 'lucide-react'

const NotFoundPage: React.FC = () => {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <p className="label-caps mb-2">Route Not Found</p>
        <h1 className="text-7xl font-bold text-white font-data">404</h1>
        <p className="text-muted mt-3 text-sm">This console route doesn't exist.</p>

        <div className="flex gap-3 justify-center mt-8">
          <button
            onClick={() => navigate(-1)}
            className="btn-secondary flex items-center gap-2"
          >
            <ArrowLeft size={16} />
            Go Back
          </button>
          <button
            onClick={() => navigate('/dashboard')}
            className="btn-primary flex items-center gap-2"
          >
            <Home size={16} />
            Operations Center
          </button>
        </div>
      </div>
    </div>
  )
}

export default NotFoundPage
