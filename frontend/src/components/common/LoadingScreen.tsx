// frontend/src/components/common/LoadingScreen.tsx

import React from 'react'
import { Loader2 } from 'lucide-react'

const LoadingScreen: React.FC = () => {
  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="flex flex-col items-center gap-4">
        <Loader2 className="animate-spin text-blue-500" size={48} />
        <p className="text-muted">Loading TrackX...</p>
      </div>
    </div>
  )
}

export default LoadingScreen
