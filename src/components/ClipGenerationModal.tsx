import React, { useState, useEffect } from 'react'
import { X, Scissors, Download, Settings, Play, Pause, Volume2, VolumeX, Sparkles, Zap, Target, Award } from 'lucide-react'
import { toast } from 'sonner'
import { apiService } from '../services/api'
import { webSocketService } from '../services/websocket'

interface ClipGenerationOptions {
  duration: number
  format: 'mp4' | 'webm' | 'mov'
  quality: 'high' | 'medium' | 'low'
  resolution: '1080p' | '720p' | '480p'
  includeSubtitles: boolean
  includeBranding: boolean
  customIntro: boolean
  customOutro: boolean
  platform: 'tiktok' | 'youtube' | 'instagram' | 'twitter' | 'custom'
  aspectRatio: '16:9' | '9:16' | '1:1' | '4:5'
  addCaptions: boolean
  enhanceAudio: boolean
  addTransitions: boolean
  autoThumbnail: boolean
}

interface ClipGenerationModalProps {
  isOpen: boolean
  onClose: () => void
  segment: any
  jobId: string
  onClipGenerated: () => void
}

const ClipGenerationModal: React.FC<ClipGenerationModalProps> = ({
  isOpen,
  onClose,
  segment,
  jobId,
  onClipGenerated
}) => {
  const [options, setOptions] = useState<ClipGenerationOptions>({
    duration: 30,
    format: 'mp4',
    quality: 'high',
    resolution: '1080p',
    includeSubtitles: true,
    includeBranding: false,
    customIntro: false,
    customOutro: false,
    platform: 'tiktok',
    aspectRatio: '9:16',
    addCaptions: true,
    enhanceAudio: true,
    addTransitions: false,
    autoThumbnail: true
  })
  
  const [generating, setGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState('')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [estimatedTime, setEstimatedTime] = useState(0)
  const [activeTab, setActiveTab] = useState<'basic' | 'advanced' | 'platform'>('basic')

  // Platform-specific presets
  const platformPresets = {
    tiktok: {
      aspectRatio: '9:16' as const,
      duration: 30,
      resolution: '1080p' as const,
      addCaptions: true,
      enhanceAudio: true
    },
    youtube: {
      aspectRatio: '16:9' as const,
      duration: 60,
      resolution: '1080p' as const,
      addCaptions: true,
      enhanceAudio: false
    },
    instagram: {
      aspectRatio: '9:16' as const,
      duration: 30,
      resolution: '1080p' as const,
      addCaptions: true,
      enhanceAudio: true
    },
    twitter: {
      aspectRatio: '16:9' as const,
      duration: 45,
      resolution: '720p' as const,
      addCaptions: false,
      enhanceAudio: false
    },
    custom: {
      aspectRatio: '16:9' as const,
      duration: 60,
      resolution: '1080p' as const,
      addCaptions: false,
      enhanceAudio: false
    }
  }

  // WebSocket subscription for progress updates
  useEffect(() => {
    if (!generating) return

    const unsubscribe = webSocketService.subscribe('clip_progress', (data) => {
      if (data.job_id === jobId && data.segment_id === segment.id) {
        setProgress(data.progress)
        setCurrentStep(data.step || '')
        setEstimatedTime(data.estimated_time || 0)
      }
    })

    const unsubscribeComplete = webSocketService.subscribe('clip_generated', (data) => {
      if (data.job_id === jobId && data.segment_id === segment.id) {
        setGenerating(false)
        setProgress(100)
        setCurrentStep('Complete!')
        toast.success('Clip generated successfully!')
        onClipGenerated()
        onClose()
      }
    })

    return () => {
      unsubscribe()
      unsubscribeComplete()
    }
  }, [generating, jobId, segment.id, onClipGenerated, onClose])

  // Update options when platform changes
  useEffect(() => {
    if (options.platform !== 'custom') {
      const preset = platformPresets[options.platform]
      setOptions(prev => ({ ...prev, ...preset }))
    }
  }, [options.platform])

  // Calculate estimated processing time
  useEffect(() => {
    const baseTime = options.duration * 2 // 2 seconds per second of video
    const qualityMultiplier = options.quality === 'high' ? 1.5 : options.quality === 'medium' ? 1 : 0.7
    const featuresMultiplier = (
      (options.addCaptions ? 1.2 : 1) *
      (options.enhanceAudio ? 1.3 : 1) *
      (options.addTransitions ? 1.1 : 1) *
      (options.includeSubtitles ? 1.1 : 1)
    )
    
    setEstimatedTime(Math.ceil(baseTime * qualityMultiplier * featuresMultiplier))
  }, [options])

  const handlePlatformChange = (platform: ClipGenerationOptions['platform']) => {
    setOptions(prev => ({ ...prev, platform }))
  }

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      setProgress(0)
      setCurrentStep('Initializing...')
      
      const clipData = {
        job_id: jobId,
        segment_id: segment.id,
        start_time: segment.start_time,
        end_time: segment.end_time,
        options: {
          ...options,
          // Adjust duration based on segment length
          duration: Math.min(options.duration, segment.duration)
        }
      }
      
      await apiService.generateClip(clipData)
      toast.success('Clip generation started!')
    } catch (err) {
      console.error('Error generating clip:', err)
      toast.error(err instanceof Error ? err.message : 'Failed to generate clip')
      setGenerating(false)
      setProgress(0)
      setCurrentStep('')
    }
  }

  const handlePreview = async () => {
    try {
      const previewData = await apiService.generatePreview({
        job_id: jobId,
        segment_id: segment.id,
        start_time: segment.start_time,
        end_time: Math.min(segment.start_time + 10, segment.end_time), // 10 second preview
        options: { ...options, quality: 'medium' }
      })
      
      setPreviewUrl(previewData.preview_url)
      toast.success('Preview generated!')
    } catch (err) {
      console.error('Error generating preview:', err)
      toast.error('Failed to generate preview')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Generate Clip</h2>
            <p className="text-gray-600 mt-1">
              {segment.title} • {Math.floor(segment.duration)}s
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex h-[600px]">
          {/* Left Panel - Options */}
          <div className="w-2/3 p-6 overflow-y-auto">
            {/* Tabs */}
            <div className="flex space-x-1 mb-6 bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setActiveTab('basic')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'basic'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Basic
              </button>
              <button
                onClick={() => setActiveTab('platform')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'platform'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Platform
              </button>
              <button
                onClick={() => setActiveTab('advanced')}
                className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'advanced'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Advanced
              </button>
            </div>

            {/* Basic Tab */}
            {activeTab === 'basic' && (
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Duration (seconds)
                  </label>
                  <input
                    type="range"
                    min="10"
                    max={Math.min(120, segment.duration)}
                    value={options.duration}
                    onChange={(e) => setOptions(prev => ({ ...prev, duration: parseInt(e.target.value) }))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-sm text-gray-500 mt-1">
                    <span>10s</span>
                    <span className="font-medium">{options.duration}s</span>
                    <span>{Math.min(120, segment.duration)}s</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Quality
                    </label>
                    <select
                      value={options.quality}
                      onChange={(e) => setOptions(prev => ({ ...prev, quality: e.target.value as any }))}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="high">High (Best quality)</option>
                      <option value="medium">Medium (Balanced)</option>
                      <option value="low">Low (Fast processing)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Format
                    </label>
                    <select
                      value={options.format}
                      onChange={(e) => setOptions(prev => ({ ...prev, format: e.target.value as any }))}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="mp4">MP4 (Recommended)</option>
                      <option value="webm">WebM</option>
                      <option value="mov">MOV</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Aspect Ratio
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {(['16:9', '9:16', '1:1', '4:5'] as const).map((ratio) => (
                      <button
                        key={ratio}
                        onClick={() => setOptions(prev => ({ ...prev, aspectRatio: ratio }))}
                        className={`p-3 border rounded-lg text-sm font-medium transition-colors ${
                          options.aspectRatio === ratio
                            ? 'border-purple-500 bg-purple-50 text-purple-600'
                            : 'border-gray-300 hover:border-gray-400'
                        }`}
                      >
                        {ratio}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Platform Tab */}
            {activeTab === 'platform' && (
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Optimize for Platform
                  </label>
                  <div className="grid grid-cols-2 gap-3">
                    {Object.entries(platformPresets).map(([platform, preset]) => (
                      <button
                        key={platform}
                        onClick={() => handlePlatformChange(platform as any)}
                        className={`p-4 border rounded-lg text-left transition-colors ${
                          options.platform === platform
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-300 hover:border-gray-400'
                        }`}
                      >
                        <div className="font-medium capitalize mb-1">{platform}</div>
                        <div className="text-sm text-gray-600">
                          {preset.aspectRatio} • {preset.duration}s • {preset.resolution}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-medium text-blue-900 mb-2">Platform Optimization Score</h4>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-blue-700">Current Platform</span>
                      <span className="font-medium text-blue-900">
                        {segment.viral_metrics?.platform_optimization?.[options.platform]?.toFixed(1) || 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Advanced Tab */}
            {activeTab === 'advanced' && (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Resolution
                    </label>
                    <select
                      value={options.resolution}
                      onChange={(e) => setOptions(prev => ({ ...prev, resolution: e.target.value as any }))}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-purple-500"
                    >
                      <option value="1080p">1080p (Full HD)</option>
                      <option value="720p">720p (HD)</option>
                      <option value="480p">480p (SD)</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-4">
                  <h4 className="font-medium text-gray-900">Enhancement Options</h4>
                  
                  {[
                    { key: 'addCaptions', label: 'Auto-generated Captions', icon: Sparkles },
                    { key: 'enhanceAudio', label: 'Audio Enhancement', icon: Volume2 },
                    { key: 'addTransitions', label: 'Smooth Transitions', icon: Zap },
                    { key: 'autoThumbnail', label: 'Auto Thumbnail', icon: Target },
                    { key: 'includeSubtitles', label: 'Burned-in Subtitles', icon: Award },
                  ].map(({ key, label, icon: Icon }) => (
                    <label key={key} className="flex items-center space-x-3 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={options[key as keyof ClipGenerationOptions] as boolean}
                        onChange={(e) => setOptions(prev => ({ ...prev, [key]: e.target.checked }))}
                        className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                      />
                      <Icon className="w-4 h-4 text-gray-500" />
                      <span className="text-sm text-gray-700">{label}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Preview & Actions */}
          <div className="w-1/3 bg-gray-50 p-6 border-l border-gray-200">
            <div className="space-y-6">
              {/* Preview */}
              <div>
                <h4 className="font-medium text-gray-900 mb-3">Preview</h4>
                <div className="bg-gray-200 rounded-lg aspect-video flex items-center justify-center">
                  {previewUrl ? (
                    <video
                      src={previewUrl}
                      controls
                      className="w-full h-full rounded-lg"
                    />
                  ) : (
                    <div className="text-center">
                      <Play className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-500">No preview available</p>
                    </div>
                  )}
                </div>
                <button
                  onClick={handlePreview}
                  className="w-full mt-3 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
                >
                  Generate Preview
                </button>
              </div>

              {/* Estimated Time */}
              <div className="bg-white p-4 rounded-lg">
                <h4 className="font-medium text-gray-900 mb-2">Estimated Processing Time</h4>
                <p className="text-2xl font-bold text-purple-600">{estimatedTime}s</p>
                <p className="text-sm text-gray-500 mt-1">
                  Based on selected options
                </p>
              </div>

              {/* Progress */}
              {generating && (
                <div className="bg-white p-4 rounded-lg">
                  <h4 className="font-medium text-gray-900 mb-2">Processing</h4>
                  <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    ></div>
                  </div>
                  <p className="text-sm text-gray-600">{currentStep}</p>
                  <p className="text-xs text-gray-500 mt-1">{progress}% complete</p>
                </div>
              )}

              {/* Actions */}
              <div className="space-y-3">
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="w-full flex items-center justify-center px-4 py-3 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Scissors className="w-4 h-4 mr-2" />
                  {generating ? 'Generating...' : 'Generate Clip'}
                </button>
                
                <button
                  onClick={onClose}
                  className="w-full px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-gray-400 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ClipGenerationModal