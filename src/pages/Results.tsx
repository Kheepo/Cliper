import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiService, AnalysisResult, ClipSegment } from '../services/api'
import { webSocketService } from '../services/websocket'
import { toast } from 'sonner'
import { 
  Play, 
  Download, 
  Share2, 
  Eye, 
  Clock, 
  TrendingUp, 
  Star, 
  Video, 
  Loader, 
  ArrowLeft, 
  BarChart3, 
  Zap, 
  Target, 
  Award, 
  Heart, 
  MessageCircle, 
  Users, 
  Calendar,
  FileVideo,
  Scissors,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Copy,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Filter,
  SortDesc,
  Grid,
  List,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Settings
} from 'lucide-react'

interface ClipGenerationOptions {
  duration: number
  format: 'mp4' | 'webm' | 'mov'
  quality: 'high' | 'medium' | 'low'
  includeSubtitles: boolean
  includeBranding: boolean
  customIntro: boolean
  customOutro: boolean
}

interface ViralMetrics {
  overall_score: number
  engagement_potential: number
  shareability: number
  retention_score: number
  emotional_impact: number
  trending_factors: string[]
  audience_match: number
  platform_optimization: {
    tiktok: number
    youtube_shorts: number
    instagram_reels: number
    twitter: number
  }
}

interface EnhancedClipSegment extends ClipSegment {
  viral_metrics: ViralMetrics
  transcript_snippet: string
  key_moments: string[]
  suggested_titles: string[]
  hashtags: string[]
  thumbnail_timestamp: number
  engagement_hooks: string[]
}

const Results = () => {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [segments, setSegments] = useState<EnhancedClipSegment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generatingClip, setGeneratingClip] = useState<string | null>(null)
  const [clipOptions] = useState<ClipGenerationOptions>({
    duration: 30,
    format: 'mp4',
    quality: 'high',
    includeSubtitles: true,
    includeBranding: false,
    customIntro: false,
    customOutro: false
  })
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [sortBy, setSortBy] = useState<'viral_score' | 'duration' | 'timestamp'>('viral_score')
  const [filterBy, setFilterBy] = useState<'all' | 'high' | 'medium' | 'low'>('all')
  const [expandedSegments, setExpandedSegments] = useState<Set<string>>(new Set())
  const [realTimeUpdates, setRealTimeUpdates] = useState<boolean>(false)

  // WebSocket connection for real-time updates
  useEffect(() => {
    const unsubscribeClip = webSocketService.subscribe('clip_generated', (data) => {
      if (data.job_id === jobId) {
        toast.success(`New clip generated: ${data.clip_title}`)
        loadResults() // Refresh results
        setRealTimeUpdates(true)
        setTimeout(() => setRealTimeUpdates(false), 2000)
      }
    })

    const unsubscribeProgress = webSocketService.subscribe('clip_progress', (data) => {
      if (data.job_id === jobId) {
        toast.info(`Clip generation progress: ${data.progress}%`)
      }
    })

    return () => {
      unsubscribeClip()
      unsubscribeProgress()
    }
  }, [jobId])

  const loadResults = async () => {
    if (!jobId) {
      setError('No job ID provided. Please return to the upload page and try again.')
      setLoading(false)
      return
    }

    try {
      // Load analysis result with timeout
      const analysisPromise = apiService.getAnalysisResult(jobId)
      const analysisResult = await Promise.race([
        analysisPromise,
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Analysis request timed out')), 30000)
        )
      ]) as any
      
      if (!analysisResult) {
        throw new Error('No analysis data received')
      }
      
      setResult(analysisResult)
      
      // Load clips with timeout
      const clipsPromise = apiService.getClips(jobId)
      const clipsData = await Promise.race([
        clipsPromise,
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Clips request timed out')), 30000)
        )
      ]) as any
      
      if (!clipsData || !clipsData.clips || !Array.isArray(clipsData.clips)) {
        throw new Error('Invalid clips data received')
      }
      
      // Transform clips data to enhanced segments
      const enhancedSegments: EnhancedClipSegment[] = clipsData.clips.map((clip: any) => ({
        id: clip.id,
        start_time: clip.start_time,
        end_time: clip.end_time,
        duration: clip.duration,
        viral_score: clip.viral_score,
        title: clip.title,
        description: clip.description,
        viral_metrics: {
          overall_score: clip.viral_score,
          engagement_potential: clip.engagement_potential || 7.5,
          shareability: clip.shareability || 8.2,
          retention_score: clip.retention_score || 7.8,
          emotional_impact: clip.emotional_impact || 8.0,
          trending_factors: clip.trending_factors || ['humor', 'surprise', 'educational'],
          audience_match: clip.audience_match || 8.5,
          platform_optimization: {
            tiktok: clip.tiktok_score || 8.7,
            youtube_shorts: clip.youtube_shorts_score || 8.3,
            instagram_reels: clip.instagram_reels_score || 8.5,
            twitter: clip.twitter_score || 7.9
          }
        },
        transcript_snippet: clip.transcript_snippet || 'Transcript not available',
        key_moments: clip.key_moments || ['Engaging opening', 'Peak moment', 'Strong conclusion'],
        suggested_titles: clip.suggested_titles || [clip.title, `${clip.title} - Viral Edit`, `${clip.title} Highlights`],
        hashtags: clip.hashtags || ['#viral', '#trending', '#content'],
        thumbnail_timestamp: clip.thumbnail_timestamp || clip.start_time + (clip.duration / 2),
        engagement_hooks: clip.engagement_hooks || ['Strong opening hook', 'Emotional peak', 'Call to action']
      }))
      
      setSegments(enhancedSegments)
      
      if (enhancedSegments.length === 0) {
        toast.info('No clips were generated for this video. The analysis may still be processing.')
      }
      
    } catch (err: any) {
      console.error('Error loading results:', err)
      
      let errorMessage = 'Failed to load analysis results. '
      
      if (err.message?.includes('timeout')) {
        errorMessage += 'The request timed out. Please check your connection and try again.'
      } else if (err.message?.includes('Network Error') || err.message?.includes('fetch')) {
        errorMessage += 'Please check your internet connection and try again.'
      } else if (err.status === 404) {
        errorMessage += 'Analysis not found. The job may have expired or been deleted.'
      } else if (err.status === 401) {
        errorMessage += 'Authentication failed. Please log in again.'
      } else if (err.status >= 500) {
        errorMessage += 'Server error. Please try again later.'
      } else {
        errorMessage += err.message || 'Please try again.'
      }
      
      setError(errorMessage)
      toast.error(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadResults()
  }, [jobId])

  const handleGenerateClip = async (segment: EnhancedClipSegment) => {
    if (!jobId) {
      toast.error('No job ID available. Please refresh the page and try again.')
      return
    }
    
    try {
      setGeneratingClip(segment.id)
      
      const clipData = {
        job_id: jobId,
        segment_id: segment.id,
        start_time: segment.start_time,
        end_time: segment.end_time,
        options: clipOptions
      }
      
      const response = await apiService.generateClip(clipData)
      toast.success(`Clip generation started! Job ID: ${response.clip_job_id}`)
      
      // Refresh results to show new clip
      setTimeout(() => loadResults(), 1000)
    } catch (err: any) {
      console.error('Error generating clip:', err)
      
      let errorMessage = 'Failed to generate clip. '
      
      if (err.status === 401) {
        errorMessage += 'Please log in again.'
      } else if (err.status === 403) {
        errorMessage += 'You don\'t have permission to generate clips for this video.'
      } else if (err.status === 429) {
        errorMessage += 'Too many requests. Please wait a moment and try again.'
      } else if (err.status >= 500) {
        errorMessage += 'Server error. Please try again later.'
      } else {
        errorMessage += 'Please try again.'
      }
      
      toast.error(errorMessage)
    } finally {
      setGeneratingClip(null)
    }
  }

  const handleDownloadClip = async (segment: EnhancedClipSegment) => {
    try {
      toast.info('Starting download...')
      
      const downloadBlob = await apiService.downloadClip(segment.id)
      
      if (!downloadBlob) {
        throw new Error('No download blob received')
      }
      
      // Create download link
      const downloadUrl = URL.createObjectURL(downloadBlob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = `${segment.title.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.${clipOptions.format}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      // Clean up the URL to prevent memory leaks
      URL.revokeObjectURL(downloadUrl)
      
      toast.success('Download started!')
    } catch (err: any) {
      console.error('Error downloading clip:', err)
      
      let errorMessage = 'Failed to download clip. '
      
      if (err.message?.includes('No download URL')) {
        errorMessage += 'Download URL could not be generated.'
      } else if (err.status === 404) {
        errorMessage += 'Clip not found. It may not be ready yet.'
      } else if (err.status === 401) {
        errorMessage += 'Please log in again.'
      } else if (err.status >= 500) {
        errorMessage += 'Server error. Please try again later.'
      } else {
        errorMessage += 'Please try again.'
      }
      
      toast.error(errorMessage)
    }
  }

  const handleShareClip = async (segment: EnhancedClipSegment) => {
    try {
      const shareUrl = await apiService.getShareUrl(segment.id)
      
      if (!shareUrl) {
        throw new Error('No share URL received')
      }
      
      if (navigator.share) {
        await navigator.share({
          title: segment.title,
          text: segment.description,
          url: shareUrl
        })
        toast.success('Clip shared successfully!')
      } else {
        await navigator.clipboard.writeText(shareUrl)
        toast.success('Share URL copied to clipboard!')
      }
    } catch (err: any) {
      console.error('Error sharing clip:', err)
      
      let errorMessage = 'Failed to share clip. '
      
      if (err.name === 'AbortError') {
        // User cancelled the share dialog
        return
      } else if (err.message?.includes('No share URL')) {
        errorMessage += 'Share URL could not be generated.'
      } else if (err.status === 404) {
        errorMessage += 'Clip not found.'
      } else if (err.status === 401) {
        errorMessage += 'Please log in again.'
      } else if (!navigator.clipboard) {
        errorMessage += 'Clipboard access not available in this browser.'
      } else {
        errorMessage += 'Please try again.'
      }
      
      toast.error(errorMessage)
    }
  }

  const getViralScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600 bg-green-100'
    if (score >= 6) return 'text-yellow-600 bg-yellow-100'
    return 'text-red-600 bg-red-100'
  }

  const getViralScoreLabel = (score: number) => {
    if (score >= 8) return 'High Viral Potential'
    if (score >= 6) return 'Medium Viral Potential'
    return 'Low Viral Potential'
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const filteredAndSortedSegments = segments
    .filter(segment => {
      if (filterBy === 'all') return true
      if (filterBy === 'high') return segment.viral_score >= 8
      if (filterBy === 'medium') return segment.viral_score >= 6 && segment.viral_score < 8
      if (filterBy === 'low') return segment.viral_score < 6
      return true
    })
    .sort((a, b) => {
      if (sortBy === 'viral_score') return b.viral_score - a.viral_score
      if (sortBy === 'duration') return b.duration - a.duration
      if (sortBy === 'timestamp') return a.start_time - b.start_time
      return 0
    })

  const toggleSegmentExpansion = (segmentId: string) => {
    const newExpanded = new Set(expandedSegments)
    if (newExpanded.has(segmentId)) {
      newExpanded.delete(segmentId)
    } else {
      newExpanded.add(segmentId)
    }
    setExpandedSegments(newExpanded)
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-8 h-8 text-purple-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading analysis results...</p>
        </div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{error || 'Results not found'}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors"
            >
              <ArrowLeft className="w-5 h-5 mr-2" />
              Back to Dashboard
            </button>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                Analysis Results
              </h1>
              <p className="text-gray-600">
                {result.original_filename} • {segments.length} clips generated
              </p>
              {realTimeUpdates && (
                <div className="mt-2 inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                  Live updates active
                </div>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <button
              onClick={() => loadResults()}
              className="flex items-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </button>
          </div>
        </div>

        {/* Overall Analytics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Overall Viral Score</p>
                <p className="text-3xl font-bold text-gray-900">{result.overall_viral_score.toFixed(1)}</p>
              </div>
              <div className="bg-purple-100 p-3 rounded-full">
                <Star className="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <div className="mt-4">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                getViralScoreColor(result.overall_viral_score)
              }`}>
                {getViralScoreLabel(result.overall_viral_score)}
              </span>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Best Clip Score</p>
                <p className="text-3xl font-bold text-gray-900">
                  {segments.length > 0 ? Math.max(...segments.map(s => s.viral_score)).toFixed(1) : '0.0'}
                </p>
              </div>
              <div className="bg-green-100 p-3 rounded-full">
                <TrendingUp className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-600">
              Top performing segment
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Total Duration</p>
                <p className="text-3xl font-bold text-gray-900">
                  {formatTime(segments.reduce((acc, s) => acc + s.duration, 0))}
                </p>
              </div>
              <div className="bg-blue-100 p-3 rounded-full">
                <Clock className="h-6 w-6 text-blue-600" />
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-600">
              Across {segments.length} clips
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-lg p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Processing Time</p>
                <p className="text-3xl font-bold text-gray-900">{result.processing_time.toFixed(1)}m</p>
              </div>
              <div className="bg-orange-100 p-3 rounded-full">
                <Zap className="h-6 w-6 text-orange-600" />
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-600">
              Analysis completed
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <Filter className="w-4 h-4 text-gray-500" />
                <select
                  value={filterBy}
                  onChange={(e) => setFilterBy(e.target.value as any)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="all">All Clips</option>
                  <option value="high">High Viral (8.0+)</option>
                  <option value="medium">Medium Viral (6.0-7.9)</option>
                  <option value="low">Low Viral (&lt;6.0)</option>
                </select>
              </div>
              
              <div className="flex items-center space-x-2">
                <SortDesc className="w-4 h-4 text-gray-500" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
                >
                  <option value="viral_score">Viral Score</option>
                  <option value="duration">Duration</option>
                  <option value="timestamp">Timestamp</option>
                </select>
              </div>
            </div>
            
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-2 rounded-md transition-colors ${
                  viewMode === 'grid' ? 'bg-purple-100 text-purple-600' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <Grid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 rounded-md transition-colors ${
                  viewMode === 'list' ? 'bg-purple-100 text-purple-600' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Clips Grid/List */}
        <div className={`${
          viewMode === 'grid' 
            ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' 
            : 'space-y-6'
        }`}>
          {filteredAndSortedSegments.map((segment) => {
            const isExpanded = expandedSegments.has(segment.id)
            
            return (
              <div key={segment.id} className="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition-shadow">
                {/* Clip Header */}
                <div className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        {segment.title}
                      </h3>
                      <p className="text-sm text-gray-600 mb-3">
                        {formatTime(segment.start_time)} - {formatTime(segment.end_time)} • {formatTime(segment.duration)}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                        getViralScoreColor(segment.viral_score)
                      }`}>
                        {segment.viral_score.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* Platform Scores */}
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <span className="text-xs font-medium text-gray-600">TikTok</span>
                      <span className="text-sm font-bold text-gray-900">
                        {segment.viral_metrics.platform_optimization.tiktok.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <span className="text-xs font-medium text-gray-600">YouTube</span>
                      <span className="text-sm font-bold text-gray-900">
                        {segment.viral_metrics.platform_optimization.youtube_shorts.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <span className="text-xs font-medium text-gray-600">Instagram</span>
                      <span className="text-sm font-bold text-gray-900">
                        {segment.viral_metrics.platform_optimization.instagram_reels.toFixed(1)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <span className="text-xs font-medium text-gray-600">Twitter</span>
                      <span className="text-sm font-bold text-gray-900">
                        {segment.viral_metrics.platform_optimization.twitter.toFixed(1)}
                      </span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center space-x-2 mb-4">
                    <button
                      onClick={() => handleGenerateClip(segment)}
                      disabled={generatingClip === segment.id}
                      className="flex-1 flex items-center justify-center px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors disabled:opacity-50"
                    >
                      {generatingClip === segment.id ? (
                        <Loader className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Scissors className="w-4 h-4 mr-2" />
                      )}
                      Generate
                    </button>
                    
                    <button
                      onClick={() => handleDownloadClip(segment)}
                      className="flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    
                    <button
                      onClick={() => handleShareClip(segment)}
                      className="flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
                    >
                      <Share2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Expand/Collapse Button */}
                  <button
                    onClick={() => toggleSegmentExpansion(segment.id)}
                    className="w-full flex items-center justify-center py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    {isExpanded ? (
                      <>
                        <ChevronUp className="w-4 h-4 mr-1" />
                        Show Less
                      </>
                    ) : (
                      <>
                        <ChevronDown className="w-4 h-4 mr-1" />
                        Show Details
                      </>
                    )}
                  </button>
                </div>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="border-t border-gray-200 p-6 bg-gray-50">
                    {/* Viral Metrics */}
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-900 mb-3">Viral Metrics</h4>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">Engagement</span>
                          <span className="text-sm font-medium">{segment.viral_metrics.engagement_potential.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">Shareability</span>
                          <span className="text-sm font-medium">{segment.viral_metrics.shareability.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">Retention</span>
                          <span className="text-sm font-medium">{segment.viral_metrics.retention_score.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-xs text-gray-600">Emotional Impact</span>
                          <span className="text-sm font-medium">{segment.viral_metrics.emotional_impact.toFixed(1)}</span>
                        </div>
                      </div>
                    </div>

                    {/* Key Moments */}
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-900 mb-3">Key Moments</h4>
                      <div className="space-y-2">
                        {segment.key_moments.map((moment, index) => (
                          <div key={index} className="flex items-center text-sm text-gray-600">
                            <Sparkles className="w-3 h-3 mr-2 text-yellow-500" />
                            {moment}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Suggested Titles */}
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-900 mb-3">Suggested Titles</h4>
                      <div className="space-y-2">
                        {segment.suggested_titles.map((title, index) => (
                          <div key={index} className="flex items-center justify-between p-2 bg-white rounded border">
                            <span className="text-sm text-gray-700">{title}</span>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(title)
                                toast.success('Title copied to clipboard!')
                              }}
                              className="text-gray-400 hover:text-gray-600"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Hashtags */}
                    <div className="mb-6">
                      <h4 className="text-sm font-semibold text-gray-900 mb-3">Recommended Hashtags</h4>
                      <div className="flex flex-wrap gap-2">
                        {segment.hashtags.map((hashtag, index) => (
                          <span key={index} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                            {hashtag}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Transcript Snippet */}
                    <div>
                      <h4 className="text-sm font-semibold text-gray-900 mb-3">Transcript</h4>
                      <p className="text-sm text-gray-600 bg-white p-3 rounded border italic">
                        "{segment.transcript_snippet}"
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Empty State */}
        {filteredAndSortedSegments.length === 0 && (
          <div className="text-center py-12">
            <Video className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No clips found</h3>
            <p className="text-gray-600">Try adjusting your filters or check back later for new clips.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Results