import React, { useState } from 'react'
import { apiClient } from '../App'
import { Upload, Camera, CheckCircle, AlertCircle, Image as ImageIcon } from 'lucide-react'

export default function LiveIngestion() {
  const [selectedFile, setSelectedFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState(null)

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setResult(null)
      
      // Create preview
      const reader = new FileReader()
      reader.onloadend = () => {
        setPreview(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setProcessing(true)
    setResult(null)

    try {
      // In production, send actual file
      // For demo, just call the mock endpoint
      const response = await apiClient.post('/api/v1/upload/image')
      setResult(response.data)
      setProcessing(false)
    } catch (error) {
      console.error('Upload failed:', error)
      setResult({
        success: false,
        message: 'Failed to process image'
      })
      setProcessing(false)
    }
  }

  const handleClear = () => {
    setSelectedFile(null)
    setPreview(null)
    setResult(null)
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">Live Image Ingestion</h1>
        <p className="text-gray-400">Upload vehicle images for real-time ANPR/OCR processing</p>
      </div>

      {/* Upload Area */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left: Upload */}
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-6 flex items-center space-x-2">
            <Upload className="w-6 h-6 text-blue-500" />
            <span>Upload Image</span>
          </h2>

          <div className="space-y-6">
            {/* File Input */}
            <div
              className="border-2 border-dashed border-slate-600 rounded-lg p-12 text-center hover:border-blue-500 transition-colors cursor-pointer"
              onClick={() => document.getElementById('fileInput').click()}
            >
              {preview ? (
                <div>
                  <img src={preview} alt="Preview" className="max-h-64 mx-auto rounded-lg mb-4" />
                  <p className="text-gray-400 text-sm">{selectedFile?.name}</p>
                </div>
              ) : (
                <div>
                  <ImageIcon className="w-16 h-16 text-gray-500 mx-auto mb-4" />
                  <p className="text-white mb-2">Click to select image</p>
                  <p className="text-gray-400 text-sm">Supports JPG, PNG, WEBP</p>
                </div>
              )}
            </div>

            <input
              id="fileInput"
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
            />

            {/* Actions */}
            <div className="flex space-x-4">
              <button
                onClick={handleUpload}
                disabled={!selectedFile || processing}
                className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                  selectedFile && !processing
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-slate-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                {processing ? (
                  <span className="flex items-center justify-center space-x-2">
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                    <span>Processing...</span>
                  </span>
                ) : (
                  <span className="flex items-center justify-center space-x-2">
                    <Camera className="w-5 h-5" />
                    <span>Process Image</span>
                  </span>
                )}
              </button>

              <button
                onClick={handleClear}
                disabled={!selectedFile}
                className={`px-6 py-3 rounded-lg font-semibold transition-colors ${
                  selectedFile
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-slate-700 text-gray-500 cursor-not-allowed'
                }`}
              >
                Clear
              </button>
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-8">
          <h2 className="text-xl font-bold text-white mb-6 flex items-center space-x-2">
            <CheckCircle className="w-6 h-6 text-green-500" />
            <span>OCR Results</span>
          </h2>

          {!result && (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <AlertCircle className="w-16 h-16 mb-4" />
              <p>Upload an image to see results</p>
            </div>
          )}

          {result && result.success && (
            <div className="space-y-6">
              {/* License Plate */}
              <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg p-6 text-center">
                <p className="text-white/80 text-sm mb-2">DETECTED LICENSE PLATE</p>
                <p className="text-4xl font-bold text-white tracking-wider font-mono">
                  {result.ocr_results.plate_text}
                </p>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Confidence</p>
                  <p className="text-2xl font-bold text-green-400">
                    {(result.ocr_results.confidence * 100).toFixed(1)}%
                  </p>
                </div>

                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Processing Time</p>
                  <p className="text-2xl font-bold text-blue-400">
                    {result.ocr_results.processing_time_ms}ms
                  </p>
                </div>

                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Camera</p>
                  <p className="text-lg font-bold text-white">
                    {result.ocr_results.camera_id}
                  </p>
                </div>

                <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Timestamp</p>
                  <p className="text-xs font-semibold text-white">
                    {new Date(result.ocr_results.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>

              {/* Detection Box */}
              <div className="bg-slate-900/50 border border-slate-700 rounded-lg p-4">
                <p className="text-gray-400 text-sm mb-2">Detection Box Coordinates</p>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono text-gray-300">
                  {result.ocr_results.detection_box.map((point, idx) => (
                    <div key={idx}>
                      Point {idx + 1}: [{point[0]}, {point[1]}]
                    </div>
                  ))}
                </div>
              </div>

              {/* Success Message */}
              <div className="bg-green-600/20 border border-green-500 rounded-lg p-4">
                <div className="flex items-center space-x-2 text-green-400">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-semibold">{result.message}</span>
                </div>
                <p className="text-sm text-gray-400 mt-2">{result.note}</p>
              </div>
            </div>
          )}

          {result && !result.success && (
            <div className="flex flex-col items-center justify-center h-64">
              <AlertCircle className="w-16 h-16 text-red-500 mb-4" />
              <p className="text-red-400">{result.message}</p>
            </div>
          )}
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <h3 className="font-semibold text-white mb-3 flex items-center space-x-2">
            <Camera className="w-5 h-5 text-blue-500" />
            <span>OCR Engine</span>
          </h3>
          <p className="text-sm text-gray-400">
            Dual-engine system using LPRNet for initial detection and PaddleOCR for refinement, achieving >90% accuracy.
          </p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <h3 className="font-semibold text-white mb-3 flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span>Supported Conditions</span>
          </h3>
          <p className="text-sm text-gray-400">
            Handles varied lighting, weather, angles, motion blur, and damaged plates with robust preprocessing.
          </p>
        </div>

        <div className="bg-slate-800/50 backdrop-blur border border-slate-700 rounded-lg p-6">
          <h3 className="font-semibold text-white mb-3 flex items-center space-x-2">
            <Upload className="w-5 h-5 text-purple-500" />
            <span>Real-time Processing</span>
          </h3>
          <p className="text-sm text-gray-400">
            Average processing time <200ms per frame. Supports batch processing for video feeds.
          </p>
        </div>
      </div>

      {/* Demo Note */}
      <div className="bg-blue-600/20 border border-blue-500 rounded-lg p-6">
        <div className="flex items-start space-x-3">
          <AlertCircle className="w-6 h-6 text-blue-400 flex-shrink-0 mt-1" />
          <div>
            <p className="text-blue-300 font-semibold mb-2">Demo Mode Active</p>
            <p className="text-gray-300 text-sm">
              This interface demonstrates the live ingestion feature. In production deployment, the actual OCR engines (LPRNet + PaddleOCR) 
              will process uploaded images in real-time. The current demo returns mock results to showcase the UI and workflow.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
