// frontend/src/pages/VehiclesPage.tsx

import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/services/api'
import { Search, Loader2, Car, MapPin, Clock } from 'lucide-react'
import TrajectoryMap from '@/components/maps/TrajectoryMap'
import type { VehicleSearchResponse } from '@/types'
import { toast } from 'react-toastify'

const VehiclesPage: React.FC = () => {
  const [searchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState(searchParams.get('plate') || '')
  const [searchResults, setSearchResults] = useState<VehicleSearchResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [showMap, setShowMap] = useState(true)

  const handleSearch = async (e?: React.FormEvent) => {
    e?.preventDefault()
    
    if (!searchQuery.trim()) {
      toast.error('Please enter a license plate')
      return
    }
    
    setIsLoading(true)
    setHasSearched(true)
    
    try {
      const results = await api.searchVehicle({ plate: searchQuery.trim() })
      setSearchResults(results)
      
      if (!results.vehicle_found) {
        toast.info('Vehicle not found in database')
      } else {
        toast.success(`Found ${results.observations.length} observations for this vehicle`)
      }
    } catch (error) {
      console.error('Search failed:', error)
      toast.error('Search failed. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return 'N/A'
    const date = new Date(dateString)
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'HIGH': return 'bg-red-500/20 text-red-400'
      case 'MEDIUM': return 'bg-yellow-500/20 text-yellow-400'
      default: return 'bg-green-500/20 text-green-400'
    }
  }

  return (
    <div className="space-y-6">
      {/* Demo Mode Notice Banner */}
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-center justify-between text-amber-300 text-sm">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span><b>DEMO MODE (SIH-26127):</b> Query ANPR records across city cameras with instant Re-ID matching.</span>
        </div>
        <span className="text-xs bg-amber-500/20 px-2 py-0.5 rounded font-mono">BEL DEMO</span>
      </div>

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Vehicle Intelligence</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowMap(!showMap)}
            className="px-4 py-2 rounded-lg bg-surface-light border border-border text-sm hover:bg-surface-light/50"
          >
            {showMap ? 'Hide Map' : 'Show Map'}
          </button>
        </div>
      </div>

      {/* Search Bar */}
      <div className="card p-6">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={20} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter license plate (e.g., TN38AB1234)"
              className="w-full pl-10 pr-4 py-3 rounded-lg bg-surface-light border border-border focus:border-blue-500 focus:outline-none text-white"
              autoFocus
            />
          </div>
          <button
            type="submit"
            disabled={isLoading}
            className="px-6 py-3 rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white font-bold hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
          >
            {isLoading ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              <Search size={20} />
            )}
            Search
          </button>
        </form>
      </div>

      {hasSearched && searchResults && (
        <>
          {/* Vehicle Summary */}
          {searchResults.vehicle_found && searchResults.trajectory && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: Vehicle Info */}
              <div className="space-y-6">
                <div className="card p-6">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                      <Car size={32} className="text-white" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-white font-mono">
                        {searchResults.trajectory.plate_text}
                      </h2>
                      <span className={`text-xs px-3 py-1 rounded-full ${getRiskBadge(searchResults.trajectory.risk_level)}`}>
                        {searchResults.trajectory.risk_level}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">First Seen</span>
                      <span className="text-white text-sm flex items-center gap-2">
                        <Clock size={14} />
                        {formatDate(searchResults.trajectory.first_seen ?? '')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">Last Seen</span>
                      <span className="text-white text-sm flex items-center gap-2">
                        <Clock size={14} />
                        {formatDate(searchResults.trajectory.last_seen ?? '')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">Cameras</span>
                      <span className="text-white text-sm">{searchResults.trajectory.camera_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">Observations</span>
                      <span className="text-white text-sm">{searchResults.trajectory.observation_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">Total Journey</span>
                      <span className="text-white text-sm">{searchResults.trajectory.total_journey_time}</span>
                    </div>
                    {searchResults.trajectory.average_speed && (
                      <div className="flex items-center justify-between">
                        <span className="text-muted text-sm">Avg Speed</span>
                        <span className="text-white text-sm">{searchResults.trajectory.average_speed} km/h</span>
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <span className="text-muted text-sm">Route</span>
                      <span className="text-blue-400 text-sm font-mono">{searchResults.trajectory.route_path}</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right: Map */}
              {showMap && (
                <div className="lg:col-span-2">
                  <div className="card p-6 h-full">
                    <h3 className="text-lg font-bold text-white mb-4">Trajectory Map</h3>
                    <div className="h-[500px] rounded-lg overflow-hidden">
                      <TrajectoryMap 
                        trajectory={searchResults.trajectory} 
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Observations Timeline */}
          {searchResults.observations.length > 0 && (
            <div className="card p-6 mt-6">
              <h3 className="text-lg font-bold text-white mb-4">
                Observations ({searchResults.observations.length})
              </h3>
              
              <div className="space-y-4">
                {searchResults.observations.map((obs) => (
                  <div 
                    key={obs.id}
                    className="flex items-center gap-4 p-4 rounded-lg bg-surface-light border border-border hover:border-blue-500/50 transition-colors cursor-pointer"
                  >
                    {/* Camera Icon */}
                    <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                      <MapPin size={20} className="text-blue-400" />
                    </div>
                    
                    {/* Details */}
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white">{obs.camera_id}</span>
                        <span className="text-xs text-muted">{obs.timestamp}</span>
                      </div>
                      <div className="text-sm text-muted mt-1">
                        Plate: <span className="text-white font-mono">{obs.plate_text || 'N/A'}</span>
                        {' | '}
                        Confidence: <span className="text-green-400">{obs.confidence?.toFixed(2) || 'N/A'}</span>
                      </div>
                    </div>

                    {/* Evidence Thumbnail */}
                    {obs.annotated_output && (
                      <div className="w-24 h-16 rounded-lg overflow-hidden bg-surface">
                        <img 
                          src={obs.annotated_output} 
                          alt="Evidence"
                          className="w-full h-full object-cover"
                          onError={(e) => (e.target as HTMLImageElement).style.display = 'none'}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default VehiclesPage
