import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../App'
import { MapPin, Zap, Database } from 'lucide-react'
import MapView from '../components/MapView'

export default function VehicleTracking() {
  const navigate = useNavigate()
  const [vehicles, setVehicles] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [selectedPlate, setSelectedPlate] = useState(null)

  useEffect(() => {
    fetchVehicles()
  }, [])

  const fetchVehicles = async () => {
    try {
      const response = await apiClient.get('/api/v1/vehicles')
      setVehicles(response.data.vehicles || [])
      setLoading(false)
    } catch (error) {
      console.error('Failed to fetch vehicles:', error)
      setLoading(false)
    }
  }

  const filteredVehicles = vehicles.filter(v =>
    v.plate_text?.toLowerCase().includes(filter.toLowerCase())
  )

  const handleRowClick = (plate) => {
    // Navigate to vehicle details page
    navigate(`/vehicle/${plate}`)
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Vehicle Tracking</h1>
        <p className="text-gray-400">Real-time vehicle location and plate detection</p>
      </div>

      {/* Search */}
      <div>
        <input
          type="text"
          placeholder="Search by plate number... (e.g., TN09CX7134)"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Map showing trajectory */}
      {selectedPlate && (
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <h2 className="text-xl font-bold text-white mb-4">Vehicle Trajectory: {selectedPlate}</h2>
          <MapView searchPlate={selectedPlate} />
          <button
            onClick={() => setSelectedPlate(null)}
            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
          >
            Clear Selection
          </button>
        </div>
      )}

      {/* Vehicles Table */}
      <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700 bg-slate-900/50">
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Plate</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Camera</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Observations</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Last Seen</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-300">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-gray-400">
                    Loading vehicles...
                  </td>
                </tr>
              ) : filteredVehicles.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-gray-400">
                    No vehicles found
                  </td>
                </tr>
              ) : (
                filteredVehicles.slice(0, 20).map((vehicle, idx) => (
                  <tr 
                    key={idx} 
                    className="border-b border-slate-700 hover:bg-slate-800/50 transition-colors cursor-pointer"
                    onClick={() => handleRowClick(vehicle.plate_text)}
                  >
                    <td className="px-6 py-4">
                      <span className="font-mono font-bold text-blue-400">
                        {vehicle.plate_text}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300">
                      {vehicle.camera_id || 'N/A'}
                    </td>
                    <td className="px-6 py-4 text-gray-300">
                      <span className="bg-slate-700 px-3 py-1 rounded-full text-sm">
                        {vehicle.observation_count || 1}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-gray-300 text-sm">
                      {new Date(vehicle.last_seen).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center space-x-1 text-green-400">
                        <Zap className="w-4 h-4" />
                        <span>Active</span>
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Info */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Database className="w-6 h-6 text-blue-500" />
            <h3 className="font-semibold text-white">Total Tracked</h3>
          </div>
          <p className="text-3xl font-bold text-white">{filteredVehicles.length}</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <MapPin className="w-6 h-6 text-green-500" />
            <h3 className="font-semibold text-white">Active Now</h3>
          </div>
          <p className="text-3xl font-bold text-white">{filteredVehicles.length}</p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <div className="flex items-center space-x-3 mb-4">
            <Zap className="w-6 h-6 text-purple-500" />
            <h3 className="font-semibold text-white">Avg Confidence</h3>
          </div>
          <p className="text-3xl font-bold text-white">90.8%</p>
        </div>
      </div>
    </div>
  )
}
