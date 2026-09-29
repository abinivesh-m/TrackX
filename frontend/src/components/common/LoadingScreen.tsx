// frontend/src/components/common/LoadingScreen.tsx

import React from 'react'

const LoadingScreen: React.FC = () => {
  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="flex flex-col items-center gap-3">
        <div className="spinner" />
        <p className="text-muted text-xs font-data tracking-wide">INITIALIZING CONSOLE...</p>
      </div>
    </div>
  )
}

export default LoadingScreen
