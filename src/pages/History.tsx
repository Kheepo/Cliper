import React, { useState, useEffect, useCallback } from 'react'
import { Clock, TrendingUp, Download, Share2, Play, Eye, Calendar, Filter, Star, Award, Zap, BarChart3, Video, Search, RefreshCw, FileText, ChevronLeft, ChevronRight, ExternalLink, AlertCircle, CheckCircle, XCircle, Loader } from 'lucide-react'
import { apiService } from '../services/api'
import { webSocketService } from '../services/websocket'
import { toast } from 'sonner'
import { useAuth } from '../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

interface HistoryItem {
  id: string
  title: string
  created_at: string
  updated_at: string
  status: 'completed' | 'processing' | 'failed' | 'cancelled'
  clips_count: number
  total_duration: number
  avg_virality_score: number
  thumbnail_url?: string
  file_size: number
  processing_time?: number
  error_message?: string
  platforms: string[]
  tags: string[]
}

interface HistoryAnalytics {
  total_videos: number
  completed_videos: number
  processing_videos: number
  failed_videos: number
  total_clips: number
  avg_virality_score: number
  total_processing_time: number
  success_rate: number
  most_viral_video: HistoryItem | null
  recent_activity: Array<{
    id: string
    type: 'upload' | 'completion' | 'failure'
    video_title: string
    timestamp: string
  }>
}

interface PaginationInfo {
  current_page: number
  total_pages: number
  total_items: number
  items_per_page: number
}

const History = () => {
  const navigate = useNavigate()
  const { isAuthenticated, loading: authLoading } = useAuth()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [analytics, setAnalytics] = useState<HistoryAnalytics | null>(null)
  const [pagination, setPagination] = useState<PaginationInfo>({
    current_page: 1,
    total_pages: 1,
    total_items: 0,
    items_per_page: 12
  })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [filter, setFilter] = useState<'all' | 'completed' | 'processing' | 'failed' | 'cancelled'>('all')
  const [sortBy, setSortBy] = useState<'date' | 'score' | 'clips' | 'duration'>('date')
  const [searchQuery, setSearchQuery] = useState('')
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d' | 'all'>('30d')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  const [selectedItems, setSelectedItems] = useState<string[]>([])
  const [exporting, setExporting] = useState(false)

  // Check authentication and redirect if needed
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/login')
      return
    }
    
    if (!authLoading && isAuthenticated) {
      loadHistory()
      loadAnalytics()
      
      // Subscribe to WebSocket updates
      const unsubscribe = webSocketService.subscribe('job_status', (data) => {
        if (data.type === 'job_completed' || data.type === 'job_failed') {
          loadHistory()
          loadAnalytics()
          
          if (data.type === 'job_completed') {
            toast.success(`Video "${data.title}" processing completed!`)
          } else {
            toast.error(`Video "${data.title}" processing failed`)
          }
        }
      })

      return () => {
        unsubscribe()
      }
    }
  }, [authLoading, isAuthenticated, navigate])

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      loadHistory()
    }
  }, [authLoading, isAuthenticated, filter, sortBy, searchQuery, dateRange, pagination.current_page])

  const loadHistory = async (page: number = pagination.current_page) => {
    try {
      if (page === 1) setLoading(true)
      else setRefreshing(true)
      
      const params = {
        page,
        limit: pagination.items_per_page,
        status: filter !== 'all' ? filter : undefined,
        sort_by: sortBy,
        search: searchQuery || undefined,
        date_range: dateRange !== 'all' ? dateRange : undefined
      }
      
      const response = await apiService.getUserHistoryPaginated(page, pagination.items_per_page)
      
      setHistory(response.items || [])
      setPagination({
        current_page: response.page || 1,
        total_pages: response.total_pages || 1,
        total_items: response.total_items || 0,
        items_per_page: response.items_per_page || 12
      })
    } catch (err) {
      console.error('Failed to load history:', err)
      toast.error('Failed to load history')
      
      // Fallback to mock data
      const mockHistory: HistoryItem[] = [
        {
          id: '1',
          title: 'Marketing Video Analysis',
          created_at: '2024-01-15T10:30:00Z',
          updated_at: '2024-01-15T10:35:00Z',
          status: 'completed',
          clips_count: 5,
          total_duration: 180,
          avg_virality_score: 85,
          thumbnail_url: 'https://trae-api-sg.mchost.guru/api/ide/v1/text_to_image?prompt=marketing%20video%20thumbnail%20professional%20business&image_size=landscape_16_9',
          file_size: 52428800,
          processing_time: 300,
          platforms: ['youtube', 'tiktok', 'instagram'],
          tags: ['marketing', 'business', 'professional']
        },
        {
          id: '2',
          title: 'Product Demo Highlights',
          created_at: '2024-01-14T15:45:00Z',
          updated_at: '2024-01-14T15:50:00Z',
          status: 'completed',
          clips_count: 3,
          total_duration: 120,
          avg_virality_score: 72,
          thumbnail_url: 'https://trae-api-sg.mchost.guru/api/ide/v1/text_to_image?prompt=product%20demo%20video%20technology%20showcase&image_size=landscape_16_9',
          file_size: 41943040,
          processing_time: 240,
          platforms: ['youtube', 'linkedin'],
          tags: ['product', 'demo', 'technology']
        },
        {
          id: '3',
          title: 'Educational Content',
          created_at: '2024-01-13T09:20:00Z',
          updated_at: '2024-01-13T09:20:00Z',
          status: 'processing',
          clips_count: 0,
          total_duration: 0,
          avg_virality_score: 0,
          file_size: 67108864,
          platforms: ['youtube'],
          tags: ['education', 'tutorial']
        },
        {
          id: '4',
          title: 'Event Coverage',
          created_at: '2024-01-12T14:10:00Z',
          updated_at: '2024-01-12T14:15:00Z',
          status: 'failed',
          clips_count: 0,
          total_duration: 0,
          avg_virality_score: 0,
          file_size: 104857600,
          error_message: 'Video format not supported',
          platforms: ['youtube', 'facebook'],
          tags: ['event', 'live']
        }
      ]
      setHistory(mockHistory)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  const loadAnalytics = async () => {
    try {
      const response = await apiService.getUserAnalytics()
      setAnalytics(response)
    } catch (err) {
      console.error('Failed to load analytics:', err)
      
      // Fallback to mock analytics
      const mockAnalytics: HistoryAnalytics = {
        total_videos: 15,
        completed_videos: 12,
        processing_videos: 1,
        failed_videos: 2,
        total_clips: 45,
        avg_virality_score: 78,
        total_processing_time: 3600,
        success_rate: 80,
        most_viral_video: null,
        recent_activity: [
          {
            id: '1',
            type: 'completion',
            video_title: 'Marketing Video Analysis',
            timestamp: '2024-01-15T10:35:00Z'
          },
          {
            id: '2',
            type: 'upload',
            video_title: 'Educational Content',
            timestamp: '2024-01-13T09:20:00Z'
          }
        ]
      }
      setAnalytics(mockAnalytics)
    }
  }

  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    await Promise.all([loadHistory(1), loadAnalytics()])
    toast.success('History refreshed')
  }, [])

  const handleExport = async () => {
    try {
      setExporting(true)
      const blob = await apiService.exportUserData()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `video-history-${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('History exported successfully')
    } catch (err) {
      console.error('Export failed:', err)
      toast.error('Failed to export history')
    } finally {
      setExporting(false)
    }
  }

  const handleBulkDelete = async () => {
    if (selectedItems.length === 0) return
    
    try {
      await apiService.batchDeleteVideos(selectedItems)
      setSelectedItems([])
      loadHistory()
      toast.success(`Deleted ${selectedItems.length} videos`)
    } catch (err) {
      console.error('Bulk delete failed:', err)
      toast.error('Failed to delete videos')
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  const formatFileSize = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    if (bytes === 0) return '0 Bytes'
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100 border-green-200'
      case 'processing':
        return 'text-orange-600 bg-orange-100 border-orange-200'
      case 'failed':
        return 'text-red-600 bg-red-100 border-red-200'
      case 'cancelled':
        return 'text-gray-600 bg-gray-100 border-gray-200'
      default:
        return 'text-gray-600 bg-gray-100 border-gray-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-3 h-3 mr-1" />
      case 'processing':
        return <Loader className="w-3 h-3 mr-1 animate-spin" />
      case 'failed':
        return <XCircle className="w-3 h-3 mr-1" />
      case 'cancelled':
        return <AlertCircle className="w-3 h-3 mr-1" />
      default:
        return null
    }
  }

  const getViralityColor = (score: number) => {
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-orange-600'
    return 'text-blue-600'
  }

  const getViralityIcon = (score: number) => {
    if (score >= 80) return <Award className="w-4 h-4" />
    if (score >= 60) return <Star className="w-4 h-4" />
    return <BarChart3 className="w-4 h-4" />
  }

  // Show loading state while authentication is being checked
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="bg-white rounded-2xl p-8 shadow-xl">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 font-medium">Loading...</p>
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="bg-white rounded-2xl p-8 shadow-xl">
            <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-200 border-t-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 font-medium">Loading your history...</p>
            <p className="text-sm text-gray-500 mt-2">Gathering your video processing data</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-blue-100">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <div className="bg-gradient-to-r from-blue-600 to-orange-500 p-3 rounded-xl mr-4">
                  <Clock className="w-8 h-8 text-white" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold text-gray-900">
                    Processing History
                  </h1>
                  <p className="text-gray-600">Track your video processing journey and results</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <button
                  onClick={handleRefresh}
                  disabled={refreshing}
                  className="bg-blue-50 text-blue-600 px-4 py-2 rounded-xl font-medium hover:bg-blue-100 transition-colors flex items-center disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                
                <button
                  onClick={handleExport}
                  disabled={exporting}
                  className="bg-green-50 text-green-600 px-4 py-2 rounded-xl font-medium hover:bg-green-100 transition-colors flex items-center disabled:opacity-50"
                >
                  <Download className={`w-4 h-4 mr-2 ${exporting ? 'animate-spin' : ''}`} />
                  Export
                </button>
              </div>
            </div>
            
            {/* Analytics Overview */}
            {analytics && (
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <div className="bg-gradient-to-r from-blue-50 to-blue-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <Video className="w-5 h-5 text-blue-600 mr-2" />
                    <div>
                      <div className="text-sm text-blue-600 font-medium">Total Videos</div>
                      <div className="text-lg font-bold text-blue-800">{analytics.total_videos}</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <CheckCircle className="w-5 h-5 text-green-600 mr-2" />
                    <div>
                      <div className="text-sm text-green-600 font-medium">Completed</div>
                      <div className="text-lg font-bold text-green-800">{analytics.completed_videos}</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-orange-50 to-orange-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <TrendingUp className="w-5 h-5 text-orange-600 mr-2" />
                    <div>
                      <div className="text-sm text-orange-600 font-medium">Total Clips</div>
                      <div className="text-lg font-bold text-orange-800">{analytics.total_clips}</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-purple-50 to-purple-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <Star className="w-5 h-5 text-purple-600 mr-2" />
                    <div>
                      <div className="text-sm text-purple-600 font-medium">Avg Score</div>
                      <div className="text-lg font-bold text-purple-800">{analytics.avg_virality_score}%</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-indigo-50 to-indigo-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <Clock className="w-5 h-5 text-indigo-600 mr-2" />
                    <div>
                      <div className="text-sm text-indigo-600 font-medium">Success Rate</div>
                      <div className="text-lg font-bold text-indigo-800">{analytics.success_rate}%</div>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gradient-to-r from-pink-50 to-pink-100 rounded-xl p-4">
                  <div className="flex items-center">
                    <BarChart3 className="w-5 h-5 text-pink-600 mr-2" />
                    <div>
                      <div className="text-sm text-pink-600 font-medium">Processing</div>
                      <div className="text-lg font-bold text-pink-800">{analytics.processing_videos}</div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Filters and Controls */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6 border border-gray-100">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between space-y-4 lg:space-y-0">
            <div className="flex flex-col sm:flex-row sm:items-center space-y-4 sm:space-y-0 sm:space-x-4">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Search videos..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white w-full sm:w-64"
                />
              </div>
              
              {/* Filter */}
              <div className="flex items-center">
                <Filter className="w-4 h-4 text-gray-500 mr-2" />
                <select
                  value={filter}
                  onChange={(e) => setFilter(e.target.value as any)}
                  className="border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                >
                  <option value="all">All Status</option>
                  <option value="completed">Completed</option>
                  <option value="processing">Processing</option>
                  <option value="failed">Failed</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              
              {/* Date Range */}
              <div className="flex items-center">
                <Calendar className="w-4 h-4 text-gray-500 mr-2" />
                <select
                  value={dateRange}
                  onChange={(e) => setDateRange(e.target.value as any)}
                  className="border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                >
                  <option value="7d">Last 7 days</option>
                  <option value="30d">Last 30 days</option>
                  <option value="90d">Last 90 days</option>
                  <option value="all">All time</option>
                </select>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Sort */}
              <div className="flex items-center">
                <label className="text-sm font-medium text-gray-700 mr-2">Sort:</label>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="border border-gray-300 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
                >
                  <option value="date">Latest First</option>
                  <option value="score">Highest Score</option>
                  <option value="clips">Most Clips</option>
                  <option value="duration">Longest Duration</option>
                </select>
              </div>
              
              {/* View Mode */}
              <div className="flex items-center bg-gray-100 rounded-xl p-1">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                    viewMode === 'grid' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600'
                  }`}
                >
                  Grid
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                    viewMode === 'list' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-600'
                  }`}
                >
                  List
                </button>
              </div>
            </div>
          </div>
          
          {/* Bulk Actions */}
          {selectedItems.length > 0 && (
            <div className="mt-4 p-4 bg-blue-50 rounded-xl border border-blue-200">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-blue-700">
                  {selectedItems.length} item(s) selected
                </span>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setSelectedItems([])}
                    className="text-sm text-gray-600 hover:text-gray-800"
                  >
                    Clear
                  </button>
                  <button
                    onClick={handleBulkDelete}
                    className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 transition-colors"
                  >
                    Delete Selected
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* History Content */}
        {history.length === 0 ? (
          <div className="bg-white rounded-2xl shadow-lg p-12 text-center border border-gray-100">
            <div className="w-20 h-20 bg-gradient-to-br from-blue-100 to-orange-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <Clock className="w-10 h-10 text-blue-600" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-3">No history found</h3>
            <p className="text-gray-600 mb-8 max-w-md mx-auto leading-relaxed">
              {filter === 'all' 
                ? "Start by uploading your first video to see processing history here."
                : `No videos found with the current filters. Try adjusting your search criteria.`
              }
            </p>
            <button
              onClick={() => window.location.href = '/upload'}
              className="bg-gradient-to-r from-blue-600 to-orange-500 text-white px-8 py-3 rounded-xl font-semibold hover:shadow-lg transition-all duration-300 inline-flex items-center"
            >
              <Video className="w-5 h-5 mr-2" />
              Upload Video
            </button>
          </div>
        ) : (
          <>
            {/* History Grid/List */}
            <div className={viewMode === 'grid' ? 'grid md:grid-cols-2 lg:grid-cols-3 gap-6' : 'space-y-4'}>
              {history.map((item) => (
                <div key={item.id} className={`bg-white rounded-2xl shadow-lg overflow-hidden hover:shadow-xl transition-all duration-300 border border-gray-100 ${
                  viewMode === 'grid' ? 'transform hover:-translate-y-1' : 'flex items-center p-6'
                }`}>
                  {/* Selection Checkbox */}
                  <div className={`${viewMode === 'grid' ? 'absolute top-3 left-3 z-10' : 'mr-4'}`}>
                    <input
                      type="checkbox"
                      checked={selectedItems.includes(item.id)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedItems([...selectedItems, item.id])
                        } else {
                          setSelectedItems(selectedItems.filter(id => id !== item.id))
                        }
                      }}
                      className="w-4 h-4 text-blue-600 bg-white border-gray-300 rounded focus:ring-blue-500"
                    />
                  </div>
                  
                  {viewMode === 'grid' ? (
                    <>
                      {/* Thumbnail */}
                      <div className="relative aspect-video bg-gradient-to-br from-gray-100 to-gray-200">
                        {item.thumbnail_url ? (
                          <img
                            src={item.thumbnail_url}
                            alt={item.title}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              e.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjE4MCIgdmlld0JveD0iMCAwIDMyMCAxODAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzMjAiIGhlaWdodD0iMTgwIiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0xNDQgNzJMMTc2IDkwTDE0NCAxMDhWNzJaIiBmaWxsPSIjOUI5QkEwIi8+Cjwvc3ZnPgo='
                            }}
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center">
                            <div className="bg-white bg-opacity-90 rounded-full p-4">
                              <Play className="w-8 h-8 text-gray-400" />
                            </div>
                          </div>
                        )}
                        
                        <div className="absolute top-3 right-3">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(item.status)} flex items-center`}>
                            {getStatusIcon(item.status)}
                            {item.status}
                          </span>
                        </div>
                      </div>

                      {/* Content */}
                      <div className="p-5">
                        <h3 className="font-bold text-gray-900 mb-3 line-clamp-2 text-lg">
                          {item.title}
                        </h3>
                        
                        <div className="flex items-center text-sm text-gray-500 mb-4 bg-gray-50 px-3 py-2 rounded-lg">
                          <Calendar className="w-4 h-4 mr-2 text-blue-600" />
                          {formatDate(item.created_at)}
                        </div>
                        
                        {/* File Info */}
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-4">
                          <span>{formatFileSize(item.file_size)}</span>
                          {item.processing_time && (
                            <span>{Math.round(item.processing_time / 60)}m processing</span>
                          )}
                        </div>
                        
                        {/* Tags */}
                        {item.tags && item.tags.length > 0 && (
                          <div className="flex flex-wrap gap-1 mb-4">
                            {item.tags.slice(0, 3).map((tag, index) => (
                              <span key={index} className="px-2 py-1 bg-blue-50 text-blue-600 text-xs rounded-lg">
                                {tag}
                              </span>
                            ))}
                            {item.tags.length > 3 && (
                              <span className="px-2 py-1 bg-gray-50 text-gray-500 text-xs rounded-lg">
                                +{item.tags.length - 3}
                              </span>
                            )}
                          </div>
                        )}

                        {item.status === 'completed' && (
                          <>
                            {/* Stats */}
                            <div className="grid grid-cols-2 gap-4 mb-4">
                              <div className="bg-blue-50 rounded-xl p-3 text-center">
                                <div className="text-xl font-bold text-blue-600">{item.clips_count}</div>
                                <div className="text-xs text-blue-600 font-medium">Clips</div>
                              </div>
                              <div className="bg-orange-50 rounded-xl p-3 text-center">
                                <div className={`text-xl font-bold flex items-center justify-center ${getViralityColor(item.avg_virality_score)}`}>
                                  {getViralityIcon(item.avg_virality_score)}
                                  <span className="ml-1">{item.avg_virality_score}%</span>
                                </div>
                                <div className="text-xs text-orange-600 font-medium">Avg Score</div>
                              </div>
                            </div>

                            {/* Duration */}
                            <div className="flex items-center justify-center text-sm text-gray-600 mb-4 bg-gray-50 px-3 py-2 rounded-lg">
                              <Clock className="w-4 h-4 mr-2 text-green-600" />
                              <span className="font-medium">Total: {formatDuration(item.total_duration)}</span>
                            </div>

                            {/* Actions */}
                            <button
                              onClick={() => window.location.href = `/results?job=${item.id}`}
                              className="w-full bg-gradient-to-r from-blue-600 to-orange-500 text-white px-4 py-3 rounded-xl text-sm font-semibold hover:shadow-lg transition-all duration-300 flex items-center justify-center"
                            >
                              <Eye className="w-4 h-4 mr-2" />
                              View Results
                            </button>
                          </>
                        )}

                        {item.status === 'processing' && (
                          <div className="text-center py-6">
                            <div className="bg-orange-50 rounded-xl p-4 mb-4">
                              <div className="animate-spin rounded-full h-8 w-8 border-4 border-orange-200 border-t-orange-600 mx-auto mb-3"></div>
                              <p className="text-sm font-medium text-orange-700">Processing your video...</p>
                              <p className="text-xs text-orange-600 mt-1">This may take a few minutes</p>
                            </div>
                          </div>
                        )}

                        {(item.status === 'failed' || item.status === 'cancelled') && (
                          <div className="text-center py-6">
                            <div className="bg-red-50 rounded-xl p-4 mb-4">
                              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                {item.status === 'failed' ? (
                                  <XCircle className="w-6 h-6 text-red-600" />
                                ) : (
                                  <AlertCircle className="w-6 h-6 text-red-600" />
                                )}
                              </div>
                              <p className="text-sm font-medium text-red-700 mb-2">
                                {item.status === 'failed' ? 'Processing failed' : 'Processing cancelled'}
                              </p>
                              {item.error_message && (
                                <p className="text-xs text-red-600 mb-3">{item.error_message}</p>
                              )}
                              <button
                                onClick={() => loadHistory()}
                                className="text-sm text-blue-600 hover:text-blue-700 font-semibold bg-blue-50 px-4 py-2 rounded-lg hover:bg-blue-100 transition-colors"
                              >
                                Retry
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    /* List View */
                    <>
                      {/* Thumbnail */}
                      <div className="w-24 h-16 bg-gradient-to-br from-gray-100 to-gray-200 rounded-lg flex-shrink-0 mr-4">
                        {item.thumbnail_url ? (
                          <img
                            src={item.thumbnail_url}
                            alt={item.title}
                            className="w-full h-full object-cover rounded-lg"
                            onError={(e) => {
                              e.currentTarget.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjE4MCIgdmlld0JveD0iMCAwIDMyMCAxODAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzMjAiIGhlaWdodD0iMTgwIiBmaWxsPSIjRjNGNEY2Ii8+CjxwYXRoIGQ9Ik0xNDQgNzJMMTc2IDkwTDE0NCAxMDhWNzJaIiBmaWxsPSIjOUI5QkEwIi8+Cjwvc3ZnPgo='
                            }}
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center rounded-lg">
                            <Play className="w-6 h-6 text-gray-400" />
                          </div>
                        )}
                      </div>
                      
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <h3 className="font-bold text-gray-900 mb-1 truncate text-lg">
                              {item.title}
                            </h3>
                            <div className="flex items-center text-sm text-gray-500 mb-2">
                              <Calendar className="w-4 h-4 mr-1" />
                              {formatDate(item.created_at)}
                              <span className="mx-2">•</span>
                              <span>{formatFileSize(item.file_size)}</span>
                              {item.processing_time && (
                                <>
                                  <span className="mx-2">•</span>
                                  <span>{Math.round(item.processing_time / 60)}m processing</span>
                                </>
                              )}
                            </div>
                            
                            {/* Tags */}
                            {item.tags && item.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mb-2">
                                {item.tags.slice(0, 4).map((tag, index) => (
                                  <span key={index} className="px-2 py-1 bg-blue-50 text-blue-600 text-xs rounded">
                                    {tag}
                                  </span>
                                ))}
                                {item.tags.length > 4 && (
                                  <span className="px-2 py-1 bg-gray-50 text-gray-500 text-xs rounded">
                                    +{item.tags.length - 4}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                          
                          <div className="flex items-center space-x-4 ml-4">
                            {/* Status */}
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getStatusColor(item.status)} flex items-center`}>
                              {getStatusIcon(item.status)}
                              {item.status}
                            </span>
                            
                            {item.status === 'completed' && (
                              <>
                                {/* Stats */}
                                <div className="flex items-center space-x-4 text-sm">
                                  <div className="text-center">
                                    <div className="font-bold text-blue-600">{item.clips_count}</div>
                                    <div className="text-xs text-gray-500">Clips</div>
                                  </div>
                                  <div className="text-center">
                                    <div className={`font-bold flex items-center ${getViralityColor(item.avg_virality_score)}`}>
                                      {getViralityIcon(item.avg_virality_score)}
                                      <span className="ml-1">{item.avg_virality_score}%</span>
                                    </div>
                                    <div className="text-xs text-gray-500">Score</div>
                                  </div>
                                  <div className="text-center">
                                    <div className="font-bold text-green-600">{formatDuration(item.total_duration)}</div>
                                    <div className="text-xs text-gray-500">Duration</div>
                                  </div>
                                </div>
                                
                                {/* Action */}
                                <button
                                  onClick={() => window.location.href = `/results?job=${item.id}`}
                                  className="bg-gradient-to-r from-blue-600 to-orange-500 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:shadow-lg transition-all duration-300 flex items-center"
                                >
                                  <Eye className="w-4 h-4 mr-1" />
                                  View
                                </button>
                              </>
                            )}
                            
                            {item.status === 'processing' && (
                              <div className="flex items-center text-orange-600">
                                <Loader className="w-4 h-4 mr-2 animate-spin" />
                                <span className="text-sm font-medium">Processing...</span>
                              </div>
                            )}
                            
                            {(item.status === 'failed' || item.status === 'cancelled') && (
                              <div className="flex items-center space-x-2">
                                {item.error_message && (
                                  <div className="text-xs text-red-600 max-w-xs truncate" title={item.error_message}>
                                    {item.error_message}
                                  </div>
                                )}
                                <button
                                  onClick={() => loadHistory()}
                                  className="text-sm text-blue-600 hover:text-blue-700 font-semibold bg-blue-50 px-3 py-1 rounded hover:bg-blue-100 transition-colors"
                                >
                                  Retry
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
            
            {/* Pagination */}
            {pagination.total_pages > 1 && (
              <div className="mt-8 flex items-center justify-between bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
                <div className="text-sm text-gray-600">
                  Showing {((pagination.current_page - 1) * pagination.items_per_page) + 1} to {Math.min(pagination.current_page * pagination.items_per_page, pagination.total_items)} of {pagination.total_items} videos
                </div>
                
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => loadHistory(pagination.current_page - 1)}
                    disabled={pagination.current_page === 1 || refreshing}
                    className="flex items-center px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    Previous
                  </button>
                  
                  <div className="flex items-center space-x-1">
                    {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                      const page = i + 1
                      return (
                        <button
                          key={page}
                          onClick={() => loadHistory(page)}
                          disabled={refreshing}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                            page === pagination.current_page
                              ? 'bg-blue-600 text-white'
                              : 'text-gray-600 hover:bg-gray-100'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          {page}
                        </button>
                      )
                    })}
                    
                    {pagination.total_pages > 5 && (
                      <>
                        <span className="px-2 text-gray-500">...</span>
                        <button
                          onClick={() => loadHistory(pagination.total_pages)}
                          disabled={refreshing}
                          className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                            pagination.total_pages === pagination.current_page
                              ? 'bg-blue-600 text-white'
                              : 'text-gray-600 hover:bg-gray-100'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                        >
                          {pagination.total_pages}
                        </button>
                      </>
                    )}
                  </div>
                  
                  <button
                    onClick={() => loadHistory(pagination.current_page + 1)}
                    disabled={pagination.current_page === pagination.total_pages || refreshing}
                    className="flex items-center px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default History