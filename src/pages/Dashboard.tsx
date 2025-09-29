import React, { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiService, JobAnalytics } from '../services/api'
import { webSocketService } from '../services/websocket'
import { useAuth } from '../contexts/AuthContext'
import { toast } from 'sonner'
import { Play, Clock, TrendingUp, Download, Share2, Eye, AlertCircle, CheckCircle, Loader, BarChart3, Users, Settings, Video, Upload, Zap, Star, Award, Activity, Target, XCircle, Heart, RefreshCw, RotateCcw, X, FileText } from 'lucide-react'

interface JobStatus {
  job_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  current_step: string
  estimated_remaining: number
  created_at: string
  updated_at: string
}

interface RecentActivity {
  id: string
  type: 'upload' | 'processing' | 'completed' | 'failed'
  title: string
  timestamp: string
  clips?: number
  avgScore?: number
  progress?: number
  job_id?: string
}

const Dashboard = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { loading: authLoading, isAuthenticated } = useAuth()
  const jobId = searchParams.get('job')
  
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [analytics, setAnalytics] = useState<JobAnalytics | null>(null)
  const [recentActivity, setRecentActivity] = useState<RecentActivity[]>([])
  const [realTimeUpdates, setRealTimeUpdates] = useState<boolean>(false)

  // WebSocket connection for real-time updates
  useEffect(() => {
    const unsubscribeGeneral = webSocketService.subscribe('job_update', (data) => {
      if (data.job_id === jobId) {
        setJobStatus(prev => prev ? { ...prev, ...data } : null)
      }
      // Refresh analytics when any job updates
      loadAnalytics()
      setRealTimeUpdates(true)
      setTimeout(() => setRealTimeUpdates(false), 2000)
    })

    const unsubscribeComplete = webSocketService.subscribe('analysis_complete', (data) => {
      if (data.job_id === jobId) {
        toast.success('Analysis completed! Redirecting to results...')
        setTimeout(() => navigate(`/results/${data.job_id}`), 1500)
      }
      loadAnalytics()
    })

    const unsubscribeClip = webSocketService.subscribe('clip_generated', (data) => {
      toast.success(`New clip generated for job ${data.job_id}`)
      loadAnalytics()
    })

    return () => {
      unsubscribeGeneral()
      unsubscribeComplete()
      unsubscribeClip()
    }
  }, [jobId, navigate])

  // Load analytics data
  const loadAnalytics = async () => {
    try {
      const [analyticsData, userAnalytics] = await Promise.all([
        apiService.getJobAnalytics(),
        apiService.getUserAnalytics()
      ])
      setAnalytics(analyticsData)
      
      // Convert user analytics to recent activity
      if (userAnalytics.recent_jobs) {
        const activities: RecentActivity[] = userAnalytics.recent_jobs.map((job: any) => ({
          id: job.job_id,
          type: job.status,
          title: job.original_filename || 'Video Processing',
          timestamp: new Date(job.created_at).toLocaleString(),
          clips: job.clips_count,
          avgScore: job.avg_viral_score,
          progress: job.progress,
          job_id: job.job_id
        }))
        setRecentActivity(activities)
      }
    } catch (error) {
      console.error('Failed to load analytics:', error)
      toast.error('Failed to load dashboard analytics')
    }
  }

  // Load specific job status
  const loadJobStatus = async (jobId: string) => {
    try {
      const status = await apiService.getJobStatus(jobId)
      setJobStatus(status)
      
      if (status.status === 'completed') {
        toast.success('Video processing completed! Redirecting to results...')
        setTimeout(() => navigate(`/results/${jobId}`), 1500)
      } else if (status.status === 'failed') {
        toast.error('Video processing failed. Please try uploading again.')
      }
    } catch (error) {
      console.error('Error fetching job status:', error)
      setErrorMessage('Failed to fetch job status')
      toast.error('Error checking job status')
    }
  }

  useEffect(() => {
    const initializeDashboard = async () => {
      setLoading(true)
      
      if (jobId) {
        await loadJobStatus(jobId)
      }
      
      await loadAnalytics()
      setLoading(false)
    }

    // Only initialize dashboard after auth is loaded and user is authenticated
    if (!authLoading && isAuthenticated) {
      initializeDashboard()
    } else if (!authLoading && !isAuthenticated) {
      // Redirect to login if not authenticated
      navigate('/login')
    }
  }, [jobId, authLoading, isAuthenticated, navigate])

  const handleRestartJob = async (jobId: string) => {
    try {
      setActionLoading(jobId)
      await apiService.restartJob(jobId)
      toast.success('Job restarted successfully')
      await loadAnalytics()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restart job')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelJob = async (jobId: string) => {
    try {
      setActionLoading(jobId)
      await apiService.cancelJob(jobId)
      toast.success('Job cancelled successfully')
      await loadAnalytics()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to cancel job')
    } finally {
      setActionLoading(null)
    }
  }

  const handleViewLogs = async (jobId: string) => {
    try {
      const logs = await apiService.getJobLogs(jobId)
      toast.info(`Found ${logs.total_logs} log entries for job ${jobId}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to get job logs')
    }
  }

  const handleRestartStuckJobs = async () => {
    try {
      setActionLoading('restart-stuck')
      const result = await apiService.restartStuckJobs()
      toast.success(`Restarted ${result.restarted_jobs} stuck jobs`)
      await loadAnalytics()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to restart stuck jobs')
    } finally {
      setActionLoading(null)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <Clock className="w-6 h-6 text-yellow-500" />
      case 'processing':
        return <Loader className="w-6 h-6 text-blue-500 animate-spin" />
      case 'completed':
        return <CheckCircle className="w-6 h-6 text-green-500" />
      case 'failed':
        return <XCircle className="w-6 h-6 text-red-500" />
      default:
        return <Clock className="w-6 h-6 text-gray-500" />
    }
  }

  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return 'Queued for processing'
      case 'processing':
        return 'Analyzing your video'
      case 'completed':
        return 'Analysis complete'
      case 'failed':
        return 'Processing failed'
      default:
        return 'Unknown status'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'bg-yellow-100 text-yellow-800'
      case 'processing':
        return 'bg-blue-100 text-blue-800'
      case 'completed':
        return 'bg-green-100 text-green-800'
      case 'failed':
        return 'bg-red-100 text-red-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const clsx = (...classes: (string | undefined | null | false)[]) => {
    return classes.filter(Boolean).join(' ')
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader className="w-8 h-8 text-purple-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (errorMessage && jobId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{errorMessage}</p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700"
          >
            Go Home
          </button>
        </div>
      </div>
    )
  }

  // If we have a specific job ID, show job tracking
  if (jobId && jobStatus) {
    return (
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="bg-white rounded-lg shadow-sm p-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">
                Processing Your Video
              </h1>
              <p className="text-gray-600">
                Our AI is analyzing your content to create viral clips
              </p>
              {realTimeUpdates && (
                <div className="mt-2 inline-flex items-center px-3 py-1 rounded-full text-sm bg-green-100 text-green-800">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
                  Live updates active
                </div>
              )}
            </div>

            {/* Job Status Card */}
            <div className="bg-gray-50 rounded-lg p-6 mb-8">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-3">
                  {getStatusIcon(jobStatus.status)}
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      Job #{jobStatus.job_id.slice(0, 8)}
                    </h3>
                    <p className="text-sm text-gray-500">
                      Created: {formatDate(jobStatus.created_at)}
                    </p>
                    <p className="text-sm text-gray-500">
                      Current Step: {jobStatus.current_step}
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'px-3 py-1 rounded-full text-sm font-medium',
                  getStatusColor(jobStatus.status)
                )}>
                  {getStatusText(jobStatus.status)}
                </span>
              </div>

              {/* Progress Bar */}
              <div className="mb-4">
                <div className="flex justify-between text-sm text-gray-600 mb-2">
                  <span>Progress</span>
                  <span>{jobStatus.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={clsx(
                      'h-2 rounded-full transition-all duration-300',
                      jobStatus.status === 'failed' ? 'bg-red-500' : 'bg-purple-600'
                    )}
                    style={{ width: `${jobStatus.progress}%` }}
                  ></div>
                </div>
              </div>

              <div className="flex items-center gap-2 flex-wrap">
                {jobStatus.status === 'completed' && (
                  <button
                    onClick={() => navigate(`/results/${jobStatus.job_id}`)}
                    className="flex items-center justify-center px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    View Results
                  </button>
                )}
                
                {jobStatus.status !== 'completed' && (
                  <button
                    onClick={() => handleRestartJob(jobStatus.job_id)}
                    disabled={actionLoading === jobStatus.job_id}
                    className="flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
                  >
                    {actionLoading === jobStatus.job_id ? (
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <RotateCcw className="w-4 h-4 mr-2" />
                    )}
                    Restart
                  </button>
                )}
                
                {jobStatus.status === 'processing' && (
                  <button
                    onClick={() => handleCancelJob(jobStatus.job_id)}
                    disabled={actionLoading === jobStatus.job_id}
                    className="flex items-center justify-center px-4 py-2 border border-red-300 text-red-600 rounded-md hover:border-red-500 hover:text-red-700 transition-colors"
                  >
                    {actionLoading === jobStatus.job_id ? (
                      <Loader className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <X className="w-4 h-4 mr-2" />
                    )}
                    Cancel
                  </button>
                )}
                
                <button
                  onClick={() => handleViewLogs(jobStatus.job_id)}
                  className="flex items-center justify-center px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:border-purple-500 hover:text-purple-600 transition-colors"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Logs
                </button>
              </div>
            </div>

            {/* Processing Steps */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Processing Steps
              </h3>
              
              <div className="space-y-3">
                {[
                  { step: 'Video Upload', completed: jobStatus.progress >= 20 },
                  { step: 'Content Analysis', completed: jobStatus.progress >= 40 },
                  { step: 'Moment Detection', completed: jobStatus.progress >= 60 },
                  { step: 'Virality Scoring', completed: jobStatus.progress >= 80 },
                  { step: 'Clip Generation', completed: jobStatus.progress >= 100 },
                ].map((item, index) => (
                  <div key={index} className="flex items-center space-x-3">
                    <div className={clsx(
                      'w-6 h-6 rounded-full flex items-center justify-center',
                      item.completed
                        ? 'bg-green-100 text-green-600'
                        : 'bg-gray-100 text-gray-400'
                    )}>
                      {item.completed ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : (
                        <div className="w-2 h-2 bg-current rounded-full"></div>
                      )}
                    </div>
                    <span className={clsx(
                      'text-sm',
                      item.completed ? 'text-gray-900' : 'text-gray-500'
                    )}>
                      {item.step}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Estimated Time */}
            {jobStatus.status === 'processing' && jobStatus.estimated_remaining > 0 && (
              <div className="mt-8 p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center space-x-2">
                  <Clock className="w-5 h-5 text-blue-600" />
                  <span className="text-sm font-medium text-blue-900">
                    Estimated time remaining: {Math.ceil(jobStatus.estimated_remaining)} minutes
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // Default dashboard view with real analytics
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center mb-4">
            <div className="bg-gradient-to-r from-blue-600 to-orange-500 p-3 rounded-full">
              <BarChart3 className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            Analytics Dashboard
          </h1>
          <p className="text-xl text-gray-600">
            Monitor your video processing performance and engagement metrics
          </p>
          {realTimeUpdates && (
            <div className="mt-4 inline-flex items-center px-4 py-2 rounded-full text-sm bg-green-100 text-green-800">
              <div className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></div>
              Real-time updates active
            </div>
          )}
        </div>

        {/* Enhanced Metrics Cards */}
        {analytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-lg p-6 transform transition-transform hover:scale-105">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Total Jobs</p>
                  <p className="text-3xl font-bold text-gray-900">{analytics.total_jobs}</p>
                </div>
                <div className="bg-blue-100 p-3 rounded-full">
                  <Activity className="h-6 w-6 text-blue-600" />
                </div>
              </div>
              <div className="mt-4 flex items-center text-sm">
                <span className="text-green-600 font-medium">
                  {(analytics.success_rate || 0).toFixed(1)}%
                </span>
                <span className="text-gray-600 ml-1">success rate</span>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6 transform transition-transform hover:scale-105">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Avg Viral Score</p>
                  <p className="text-3xl font-bold text-gray-900">{(analytics.average_viral_score || 0).toFixed(1)}</p>
                </div>
                <div className="bg-orange-100 p-3 rounded-full">
                  <TrendingUp className="h-6 w-6 text-orange-600" />
                </div>
              </div>
              <div className="mt-4 flex items-center text-sm">
                <span className="text-green-600 font-medium">+0.8</span>
                <span className="text-gray-600 ml-1">improvement</span>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6 transform transition-transform hover:scale-105">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Clips Generated</p>
                  <p className="text-3xl font-bold text-gray-900">{analytics.total_clips_generated || 0}</p>
                </div>
                <div className="bg-green-100 p-3 rounded-full">
                  <Video className="h-6 w-6 text-green-600" />
                </div>
              </div>
              <div className="mt-4 flex items-center text-sm">
                <span className="text-green-600 font-medium">+25%</span>
                <span className="text-gray-600 ml-1">this week</span>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-lg p-6 transform transition-transform hover:scale-105">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">Avg Processing Time</p>
                  <p className="text-3xl font-bold text-gray-900">{(analytics.average_processing_time || 0).toFixed(1)}m</p>
                </div>
                <div className="bg-purple-100 p-3 rounded-full">
                  <Clock className="h-6 w-6 text-purple-600" />
                </div>
              </div>
              <div className="mt-4 flex items-center text-sm">
                <span className="text-green-600 font-medium">-15%</span>
                <span className="text-gray-600 ml-1">faster</span>
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Enhanced Processing Status */}
          {analytics && (
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-6">Processing Status</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                  <div className="flex items-center">
                    <CheckCircle className="h-5 w-5 text-green-600 mr-3" />
                    <span className="font-medium text-gray-900">Completed</span>
                  </div>
                  <span className="text-2xl font-bold text-green-600">{analytics.completed_jobs || 0}</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                  <div className="flex items-center">
                    <Clock className="h-5 w-5 text-blue-600 mr-3" />
                    <span className="font-medium text-gray-900">Processing</span>
                  </div>
                  <span className="text-2xl font-bold text-blue-600">{analytics.processing_jobs || 0}</span>
                </div>
                
                <div className="flex items-center justify-between p-4 bg-red-50 rounded-lg">
                  <div className="flex items-center">
                    <XCircle className="h-5 w-5 text-red-600 mr-3" />
                    <span className="font-medium text-gray-900">Failed</span>
                  </div>
                  <span className="text-2xl font-bold text-red-600">{analytics.failed_jobs || 0}</span>
                </div>
              </div>
            </div>
          )}

          {/* Enhanced Recent Activity */}
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-6">Recent Activity</h2>
            <div className="space-y-4">
              {recentActivity.length > 0 ? (
                recentActivity.slice(0, 5).map((activity) => (
                  <div key={activity.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                    <div className="flex items-center">
                      <div className={`p-2 rounded-full mr-3 ${
                        activity.type === 'completed' ? 'bg-green-100' : 
                        activity.type === 'failed' ? 'bg-red-100' : 'bg-blue-100'
                      }`}>
                        {activity.type === 'completed' ? (
                          <CheckCircle className="h-4 w-4 text-green-600" />
                        ) : activity.type === 'failed' ? (
                          <XCircle className="h-4 w-4 text-red-600" />
                        ) : (
                          <Clock className="h-4 w-4 text-blue-600" />
                        )}
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{activity.title}</p>
                        <p className="text-sm text-gray-600">{activity.timestamp}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      {activity.clips && (
                        <p className="text-sm font-medium text-gray-900">{activity.clips} clips</p>
                      )}
                      {activity.avgScore && (
                        <p className="text-sm text-gray-600">Score: {activity.avgScore}</p>
                      )}
                      {activity.progress && activity.type === 'processing' && (
                        <p className="text-sm text-blue-600">{activity.progress}%</p>
                      )}
                      {activity.job_id && (
                        <button
                          onClick={() => navigate(`/results/${activity.job_id}`)}
                          className="text-xs text-purple-600 hover:text-purple-800 mt-1"
                        >
                          View Details
                        </button>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Activity className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No recent activity</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Enhanced Quick Actions */}
        <div className="mt-8 bg-white rounded-xl shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <button
              onClick={() => navigate('/upload')}
              className="flex items-center justify-center p-4 bg-gradient-to-r from-blue-600 to-orange-500 text-white rounded-lg font-medium hover:shadow-lg transition-all transform hover:scale-105"
            >
              <Upload className="h-5 w-5 mr-2" />
              Upload New Video
            </button>
            
            <button
              onClick={() => navigate('/history')}
              className="flex items-center justify-center p-4 border-2 border-gray-300 text-gray-700 rounded-lg font-medium hover:border-blue-500 hover:text-blue-600 transition-colors"
            >
              <BarChart3 className="h-5 w-5 mr-2" />
              View History
            </button>
            
            <button
              onClick={() => navigate('/settings')}
              className="flex items-center justify-center p-4 border-2 border-gray-300 text-gray-700 rounded-lg font-medium hover:border-blue-500 hover:text-blue-600 transition-colors"
            >
              <Settings className="h-5 w-5 mr-2" />
              Settings
            </button>
            
            <button
              onClick={handleRestartStuckJobs}
              disabled={actionLoading === 'restart-stuck'}
              className="flex items-center justify-center p-4 border-2 border-orange-500 text-orange-600 rounded-lg font-medium hover:bg-orange-50 transition-colors disabled:opacity-50"
            >
              {actionLoading === 'restart-stuck' ? (
                <Loader className="h-5 w-5 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-5 w-5 mr-2" />
              )}
              Restart Stuck Jobs
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard