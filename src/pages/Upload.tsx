import React, { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Upload as UploadIcon, Settings, Play, Clock, Zap, FileVideo, Globe, Star, Target, Award, TrendingUp, CheckCircle, Sparkles } from 'lucide-react'
import { apiService } from '../services/api'
import { resumableUploadService } from '../services/resumableUpload'
import { chunkedUploadService } from '../services/chunkedUpload'
import { useAuth } from '../contexts/AuthContext'
import AuthDebug from '../components/AuthDebug'
import { retryService } from '../services/retryService'
import { ErrorCategorizationService, ErrorCategory } from '../services/errorCategorization'

const Upload = () => {
  const navigate = useNavigate()
  const { user, isAuthenticated, refreshSession, loading: authLoading, maintenanceMode } = useAuth()
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [isProcessingUrl, setIsProcessingUrl] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [chunkProgress, setChunkProgress] = useState({ current: 0, total: 0 })
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [niche, setNiche] = useState('general')
  const [qualityPreset, setQualityPreset] = useState('balanced')
  const [clipDuration, setClipDuration] = useState('30-60')
  const [outputFormat, setOutputFormat] = useState('mp4')
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Check authentication status after auth loading is complete (skip in maintenance mode)
  React.useEffect(() => {
    if (!authLoading && !isAuthenticated && !maintenanceMode) {
      // Redirect to login if not authenticated and not in maintenance mode
      navigate('/login')
    }
  }, [authLoading, isAuthenticated, maintenanceMode, navigate])

  // Show loading state while authentication is being checked
  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      // Validate file type
      const allowedTypes = ['video/mp4', 'video/mov', 'video/avi', 'video/quicktime', 'video/x-msvideo']
      if (!allowedTypes.includes(file.type)) {
        setUploadError('Unsupported file format. Please use MP4, MOV, or AVI files.')
        toast.error('Unsupported file format', {
          description: 'Please select an MP4, MOV, or AVI file',
          duration: 4000
        })
        return
      }
      
      // Validate file size (2GB limit)
      const maxSize = 2 * 1024 * 1024 * 1024 // 2GB in bytes
      if (file.size > maxSize) {
        setUploadError('File is too large. Maximum file size is 2GB.')
        toast.error('File too large', {
          description: 'Please select a file smaller than 2GB',
          duration: 4000
        })
        return
      }
      
      // Validate minimum file size (1MB)
      const minSize = 1 * 1024 * 1024 // 1MB in bytes
      if (file.size < minSize) {
        setUploadError('File is too small. Minimum file size is 1MB.')
        toast.error('File too small', {
          description: 'Please select a file larger than 1MB',
          duration: 4000
        })
        return
      }
      
      setSelectedFile(file)
      setUploadError(null)
      
      // Show success feedback
      toast.success('File selected successfully', {
        description: `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`,
        duration: 3000
      })
    }
  }

  const handleFileDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const file = event.dataTransfer.files[0]
    if (file) {
      // Validate file type
      const allowedTypes = ['video/mp4', 'video/mov', 'video/avi', 'video/quicktime', 'video/x-msvideo']
      if (!allowedTypes.includes(file.type)) {
        setUploadError('Unsupported file format. Please use MP4, MOV, or AVI files.')
        toast.error('Unsupported file format', {
          description: 'Please drop an MP4, MOV, or AVI file',
          duration: 4000
        })
        return
      }
      
      // Validate file size (2GB limit)
      const maxSize = 2 * 1024 * 1024 * 1024 // 2GB in bytes
      if (file.size > maxSize) {
        setUploadError('File is too large. Maximum file size is 2GB.')
        toast.error('File too large', {
          description: 'Please drop a file smaller than 2GB',
          duration: 4000
        })
        return
      }
      
      // Validate minimum file size (1MB)
      const minSize = 1 * 1024 * 1024 // 1MB in bytes
      if (file.size < minSize) {
        setUploadError('File is too small. Minimum file size is 1MB.')
        toast.error('File too small', {
          description: 'Please drop a file larger than 1MB',
          duration: 4000
        })
        return
      }
      
      setSelectedFile(file)
      setUploadError(null)
      
      // Show success feedback
      toast.success('File dropped successfully', {
        description: `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`,
        duration: 3000
      })
    }
  }

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault()
  }

  const handleUpload = async () => {
    if (!selectedFile) return
    
    // Check authentication before upload (skip in maintenance mode)
    if (!isAuthenticated && !maintenanceMode) {
      toast.error('Authentication required', {
        description: 'Please sign in to upload videos',
        duration: 5000
      })
      return
    }
    
    setIsUploading(true)
    setUploadProgress(0)
    setChunkProgress({ current: 0, total: 0 })
    setUploadError(null)
    
    let response: { job_id: string } | null = null
    
    try {
      // Refresh session to ensure valid token
      await refreshSession()
      
      // Show upload start notification
      toast.success('Upload started!', {
        description: `Processing ${selectedFile.name}`,
        duration: 3000
      })
      
      // Use chunked upload for files larger than 10MB for better reliability
      const useChunkedUpload = selectedFile.size > 10 * 1024 * 1024;
      
      if (useChunkedUpload) {
        // Use enhanced chunked upload service
        toast.info('Using chunked upload', {
          description: 'Enhanced reliability for your file',
          duration: 3000
        });
        
        response = await chunkedUploadService.uploadFile(selectedFile, {
          niche,
          quality: qualityPreset,
          onProgress: (progress) => {
            setUploadProgress(progress)
          },
          onChunkProgress: (chunkIndex, totalChunks) => {
            setChunkProgress({ current: chunkIndex + 1, total: totalChunks })
          }
        });
        
        // Store session ID for potential resume
        const { sessionId } = await chunkedUploadService.startUpload(selectedFile, {
          niche,
          quality: qualityPreset
        })
        setCurrentSessionId(sessionId)
        
      } else {
        // Use regular upload for smaller files with enhanced error handling
        response = await apiService.uploadVideo(
          selectedFile,
          (progress) => {
            setUploadProgress(progress)
          },
          { niche, quality: qualityPreset }
        );
      }
      
      // Show upload completion and start processing monitoring
      setUploadProgress(100)
      toast.success('Upload completed!', {
        description: 'Starting video processing...',
        duration: 2000
      })
      
      // Monitor processing with timeout (5 minutes)
      try {
        await apiService.monitorProcessing(
          response.job_id,
          (status) => {
            // Update progress based on processing status
            toast.info(`Processing: ${status.status}`, {
              description: status.progress_message || 'Processing your video...',
              duration: 2000
            })
          }
        )
        
        // Processing completed successfully
        toast.success('Processing completed!', {
          description: 'Redirecting to results page...',
          duration: 2000
        })
        
        // Navigate to results page with job ID
        navigate(`/results/${response.job_id}`, {
          state: {
            jobId: response.job_id,
            filename: selectedFile.name,
            uploadMethod: 'file',
            settings: {
              niche,
              qualityPreset,
              clipDuration,
              outputFormat
            }
          }
        })
        
      } catch (processingError) {
        console.error('Processing error:', processingError)
        
        // Show processing error but still navigate to results page
        toast.error('Processing timeout or error', {
          description: 'You can check the status on the results page',
          duration: 4000
        })
        
        // Navigate to results page even if processing times out
        if (response) {
          navigate(`/results/${response.job_id}`, {
            state: {
              jobId: response.job_id,
              filename: selectedFile.name,
              uploadMethod: 'file',
              processingError: true,
              settings: {
                niche,
                qualityPreset,
                clipDuration,
                outputFormat
              }
            }
          })
        }
      }
      
    } catch (error) {
      console.error('Upload error:', error)
      
      const errorCategorization = new ErrorCategorizationService()
      const categorizedError = errorCategorization.categorizeError(
        error,
        undefined,
        {
          fileName: selectedFile?.name,
          fileSize: selectedFile?.size,
          operation: 'file_upload'
        }
      )
      
      // Handle authentication errors with session refresh
      if (categorizedError.category === ErrorCategory.AUTHENTICATION) {
        try {
          await refreshSession()
          toast.info('Session refreshed', {
            description: 'Please try uploading again',
            duration: 3000
          })
        } catch (refreshError) {
          toast.error('Please sign in again', {
            description: 'Your session has expired',
            duration: 5000
          })
        }
      }
      
      // Show appropriate toast notification based on error category
      if (categorizedError.retryable) {
        toast.error(categorizedError.userMessage, {
          description: categorizedError.suggestedAction,
          duration: 8000,
          action: currentSessionId ? {
            label: 'Resume',
            onClick: () => {
              if (selectedFile && currentSessionId) {
                chunkedUploadService.resumeUpload(currentSessionId, selectedFile)
                  .then(() => {
                    toast.success('Upload resumed successfully')
                  })
                  .catch((resumeError) => {
                    toast.error('Failed to resume upload', {
                      description: resumeError.message
                    })
                  })
              }
            }
          } : {
            label: 'Retry',
            onClick: () => {
              if (selectedFile) {
                handleUpload()
              }
            }
          }
        })
      } else {
        toast.error(categorizedError.userMessage, {
          description: categorizedError.suggestedAction,
          duration: 8000
        })
      }
      
      setUploadError(categorizedError.userMessage)
      setIsUploading(false)
      setUploadProgress(0)
      setChunkProgress({ current: 0, total: 0 })
    } finally {
      setIsUploading(false)
    }
  }

  const handleUrlSubmit = async () => {
    const trimmedUrl = videoUrl.trim()
    
    // Validate URL input
    if (!trimmedUrl) {
      setUrlError('Please enter a video URL')
      toast.error('URL required', {
        description: 'Please enter a valid video URL',
        duration: 3000
      })
      return
    }
    
    // Validate URL format
    try {
      const url = new URL(trimmedUrl)
      const supportedDomains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'tiktok.com',
        'instagram.com', 'facebook.com', 'twitter.com', 'x.com'
      ]
      
      const isSupported = supportedDomains.some(domain => 
        url.hostname.includes(domain) || url.hostname.endsWith(domain)
      )
      
      if (!isSupported && !url.pathname.match(/\.(mp4|mov|avi|webm|mkv)$/i)) {
        setUrlError('Unsupported platform or URL format. Please use YouTube, Vimeo, TikTok, or direct video links.')
        toast.error('Unsupported URL', {
          description: 'Please use a supported platform or direct video link',
          duration: 4000
        })
        return
      }
    } catch (urlError) {
      setUrlError('Invalid URL format. Please enter a valid video URL.')
      toast.error('Invalid URL', {
        description: 'Please enter a properly formatted URL',
        duration: 3000
      })
      return
    }
    
    // Check authentication before URL processing (skip in maintenance mode)
    if (!isAuthenticated && !maintenanceMode) {
      toast.error('Authentication required', {
        description: 'Please sign in to process videos from URLs',
        duration: 5000
      })
      return
    }
    
    setIsProcessingUrl(true)
    setUrlError(null)
    
    let response: { job_id: string } | null = null
    
    try {
      // Show processing start notification
      toast.success('URL processing started!', {
        description: `Processing video from URL`,
        duration: 3000
      })
      
      // Use enhanced retry service for URL processing
      const urlOperation = async () => {
        return await apiService.processUrl(trimmedUrl, { niche, quality: qualityPreset })
      }

      const result = await retryService.createApiRetryWrapper(
        urlOperation,
        'URL processing'
      )

      if (result.success) {
        response = result.data
      } else {
        throw new Error(result.error?.userMessage || 'Failed to process URL')
      }
      
      // Show URL processing completion and start monitoring
      toast.success('URL processing initiated!', {
        description: 'Starting video processing...',
        duration: 2000
      })
      
      // Monitor processing with timeout (5 minutes)
      try {
        await apiService.monitorProcessing(
          response.job_id,
          (status) => {
            // Update progress based on processing status
            toast.info(`Processing: ${status.status}`, {
              description: status.progress_message || 'Processing your video...',
              duration: 2000
            })
          }
        )
        
        // Processing completed successfully
        toast.success('Processing completed!', {
          description: 'Redirecting to results page...',
          duration: 2000
        })
        
        // Navigate to results page with job ID
        navigate(`/results/${response.job_id}`, {
          state: {
            jobId: response.job_id,
            url: trimmedUrl,
            uploadMethod: 'url',
            settings: {
              niche,
              qualityPreset,
              clipDuration,
              outputFormat
            }
          }
        })
        
      } catch (processingError) {
        console.error('Processing error:', processingError)
        
        // Show processing error but still navigate to results page
        toast.error('Processing timeout or error', {
          description: 'You can check the status on the results page',
          duration: 4000
        })
        
        // Navigate to results page even if processing times out
        if (response) {
          navigate(`/results/${response.job_id}`, {
            state: {
              jobId: response.job_id,
              url: trimmedUrl,
              uploadMethod: 'url',
              processingError: true,
              settings: {
                niche,
                qualityPreset,
                clipDuration,
                outputFormat
              }
            }
          })
        }
      }
      
    } catch (error) {
      console.error('URL processing error:', error)
      
      const errorCategorization = new ErrorCategorizationService()
      const categorizedError = errorCategorization.categorizeError(
        error,
        undefined,
        {
          operation: 'url_processing'
        }
      )
      
      // Handle authentication errors with session refresh
      if (categorizedError.category === ErrorCategory.AUTHENTICATION) {
        try {
          await refreshSession()
          toast.info('Session refreshed', {
            description: 'Please try processing the URL again',
            duration: 3000
          })
        } catch (refreshError) {
          toast.error('Please sign in again', {
            description: 'Your session has expired',
            duration: 5000
          })
        }
      }
      
      // Show appropriate toast notification based on error category
      if (categorizedError.retryable) {
        toast.error(categorizedError.userMessage, {
          description: categorizedError.suggestedAction,
          duration: 8000,
          action: {
            label: 'Retry',
            onClick: () => {
              if (videoUrl.trim()) {
                handleUrlSubmit()
              }
            }
          }
        })
      } else {
        toast.error(categorizedError.userMessage, {
          description: categorizedError.suggestedAction,
          duration: 8000
        })
      }
      
      setUrlError(categorizedError.userMessage)
      setIsProcessingUrl(false)
    } finally {
      setIsProcessingUrl(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 py-8">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Auth Debug Component */}
        {process.env.NODE_ENV === 'development' && (
          <div className="mb-8">
            <AuthDebug />
          </div>
        )}
        
        {/* Header */}
        <div className="text-center mb-12">
          <div className="w-20 h-20 bg-gradient-to-r from-blue-600 to-orange-500 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
            <UploadIcon className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Upload Your Video
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
            Transform your long-form content into viral clips with AI-powered analysis and optimization
          </p>
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          {/* Upload Section */}
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-white rounded-2xl shadow-xl border border-blue-100">
              <div className="p-8 border-b border-gray-100">
                <div className="flex items-center mb-6">
                  <div className="bg-gradient-to-r from-blue-100 to-orange-100 p-3 rounded-xl mr-4">
                    <UploadIcon className="w-6 h-6 text-blue-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-gray-900">
                    Choose Upload Method
                  </h2>
                </div>
                
                {/* Method Selection */}
                <div className="grid md:grid-cols-2 gap-6">
                  <button
                    onClick={() => setUploadMethod('file')}
                    className={`p-6 rounded-2xl border-2 transition-all duration-300 transform hover:-translate-y-1 ${
                      uploadMethod === 'file'
                        ? 'border-blue-500 bg-gradient-to-r from-blue-50 to-orange-50 shadow-lg'
                        : 'border-gray-200 hover:border-blue-300 hover:shadow-lg'
                    }`}
                  >
                    <div className="bg-gradient-to-r from-blue-100 to-blue-200 w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4">
                      <FileVideo className="w-6 h-6 text-blue-600" />
                    </div>
                    <div className="text-lg font-bold text-gray-900 mb-2">Upload File</div>
                    <div className="text-sm text-gray-600">MP4, MOV, AVI up to 2GB</div>
                    <div className="text-xs text-blue-600 mt-2 font-medium">Recommended for best quality</div>
                  </button>
                  
                  <button
                    onClick={() => setUploadMethod('url')}
                    className={`p-6 rounded-2xl border-2 transition-all duration-300 transform hover:-translate-y-1 ${
                      uploadMethod === 'url'
                        ? 'border-orange-500 bg-gradient-to-r from-orange-50 to-blue-50 shadow-lg'
                        : 'border-gray-200 hover:border-orange-300 hover:shadow-lg'
                    }`}
                  >
                    <div className="bg-gradient-to-r from-orange-100 to-orange-200 w-12 h-12 rounded-xl flex items-center justify-center mx-auto mb-4">
                      <Globe className="w-6 h-6 text-orange-600" />
                    </div>
                    <div className="text-lg font-bold text-gray-900 mb-2">From URL</div>
                    <div className="text-sm text-gray-600">YouTube, Vimeo, etc.</div>
                    <div className="text-xs text-orange-600 mt-2 font-medium">Quick and convenient</div>
                  </button>
                </div>
              </div>

              <div className="p-8">
                {uploadMethod === 'file' ? (
                  <div className="space-y-6">
                    {/* File Upload Area */}
                    <div
                      className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors cursor-pointer"
                      onDrop={handleFileDrop}
                      onDragOver={handleDragOver}
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept="video/*"
                        onChange={handleFileSelect}
                        className="hidden"
                      />
                      <UploadIcon className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                      {selectedFile ? (
                        <div>
                          <p className="text-lg font-medium text-gray-900 mb-2">{selectedFile.name}</p>
                          <p className="text-sm text-gray-500">Click to select a different file or drag and drop</p>
                        </div>
                      ) : (
                        <div>
                          <p className="text-lg font-medium text-gray-900 mb-2">Drop your video here</p>
                          <p className="text-sm text-gray-500">or click to browse files</p>
                          <p className="text-xs text-gray-400 mt-2">Supports MP4, AVI, MOV, and more</p>
                        </div>
                      )}
                    </div>
                    
                    {/* Enhanced Upload Progress */}
                    {isUploading && (
                      <div className="space-y-4">
                        <div className="flex justify-between text-sm">
                          <span className="font-medium">
                            {uploadProgress === 100 ? 'Upload Complete! Processing...' : 
                             uploadProgress > 0 ? `Uploading chunks... (${Math.round(uploadProgress)}%)` : 'Preparing upload...'}
                          </span>
                          <span className="text-blue-600 font-semibold">{Math.round(uploadProgress)}%</span>
                        </div>
                        
                        {/* Progress Bar */}
                        <div className="w-full bg-gray-200 rounded-full h-3 shadow-inner">
                          <div
                            className={`h-3 rounded-full transition-all duration-500 ease-out ${
                              uploadProgress === 100 ? 'bg-gradient-to-r from-green-500 to-green-600' : 
                              'bg-gradient-to-r from-blue-500 to-blue-600'
                            }`}
                            style={{ width: `${uploadProgress}%` }}
                          ></div>
                        </div>
                        
                        {/* Status Messages */}
                        <div className="text-xs text-gray-600 space-y-1">
                          {uploadProgress < 100 && (
                            <div className="flex items-center">
                              <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse mr-2"></div>
                              <span>Using optimized 1MB chunks for reliable upload</span>
                            </div>
                          )}
                          {uploadProgress === 100 && (
                            <div className="flex items-center justify-center text-green-600 text-sm font-medium bg-green-50 rounded-lg p-3">
                              <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                              </svg>
                              Processing your video with AI analysis...
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {/* Upload Error */}
                    {uploadError && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800 text-sm">{uploadError}</p>
                      </div>
                    )}
                    
                    {/* Upload Button */}
                    <button
                      onClick={handleUpload}
                      disabled={!selectedFile || isUploading}
                      className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      {isUploading ? 'Uploading...' : 'Start Processing'}
                    </button>
                  </div>
                ) : (
                  <div className="space-y-6">
                    {/* URL Input */}
                    <div className="space-y-4">
                      <div>
                        <label htmlFor="video-url" className="block text-sm font-medium text-gray-700 mb-2">
                          Video URL
                        </label>
                        <input
                          id="video-url"
                          type="url"
                          value={videoUrl}
                          onChange={(e) => setVideoUrl(e.target.value)}
                          placeholder="https://youtube.com/watch?v=..."
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          disabled={isProcessingUrl}
                        />
                      </div>
                      
                      <p className="text-sm text-gray-500">
                        Supports YouTube, Vimeo, TikTok, and direct video links
                      </p>
                    </div>
                    
                    {/* URL Error */}
                    {urlError && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800 text-sm">{urlError}</p>
                      </div>
                    )}
                    
                    {/* Process Button */}
                    <button
                      onClick={handleUrlSubmit}
                      disabled={!videoUrl.trim() || isProcessingUrl}
                      className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      {isProcessingUrl ? 'Processing...' : 'Start Processing'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="bg-white rounded-2xl shadow-xl border border-blue-100">
              <div className="p-8 border-b border-gray-100">
                <div className="flex items-center">
                  <div className="bg-gradient-to-r from-orange-100 to-blue-100 p-3 rounded-xl mr-4">
                    <Settings className="w-6 h-6 text-orange-600" />
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900">
                    Advanced Settings
                  </h3>
                </div>
              </div>
              
              <div className="p-8 space-y-8">
                {/* Target Niche */}
                <div>
                  <label className="block text-lg font-semibold text-gray-700 mb-4">
                    Target Niche
                  </label>
                  <select
                    value={niche}
                    onChange={(e) => setNiche(e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300 text-lg"
                  >
                    <option value="general">General Audience</option>
                    <option value="business">Business & Finance</option>
                    <option value="tech">Technology</option>
                    <option value="lifestyle">Lifestyle</option>
                    <option value="education">Education</option>
                    <option value="entertainment">Entertainment</option>
                  </select>
                </div>

                {/* Quality Preset */}
                <div>
                  <label className="block text-lg font-semibold text-gray-700 mb-4">
                    Quality Preset
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { value: 'fast', label: 'Fast', desc: 'Quick processing', icon: Zap },
                      { value: 'balanced', label: 'Balanced', desc: 'Good quality & speed', icon: Target },
                      { value: 'high', label: 'High Quality', desc: 'Best results', icon: Award }
                    ].map((preset) => {
                      const isSelected = qualityPreset === preset.value
                      const colors = {
                        fast: {
                          border: 'border-green-500',
                          bg: 'bg-gradient-to-r from-green-50 to-green-100',
                          iconBg: 'bg-gradient-to-r from-green-100 to-green-200',
                          iconText: 'text-green-600'
                        },
                        balanced: {
                          border: 'border-blue-500',
                          bg: 'bg-gradient-to-r from-blue-50 to-blue-100',
                          iconBg: 'bg-gradient-to-r from-blue-100 to-blue-200',
                          iconText: 'text-blue-600'
                        },
                        high: {
                          border: 'border-orange-500',
                          bg: 'bg-gradient-to-r from-orange-50 to-orange-100',
                          iconBg: 'bg-gradient-to-r from-orange-100 to-orange-200',
                          iconText: 'text-orange-600'
                        }
                      }
                      const colorScheme = colors[preset.value as keyof typeof colors]
                      
                      return (
                        <button
                          key={preset.value}
                          onClick={() => setQualityPreset(preset.value)}
                          className={`p-6 rounded-2xl border-2 text-center transition-all duration-300 transform hover:-translate-y-1 ${
                            isSelected
                              ? `${colorScheme.border} ${colorScheme.bg} shadow-lg`
                              : 'border-gray-200 hover:border-gray-300 hover:shadow-lg'
                          }`}
                        >
                          <div className={`w-12 h-12 ${colorScheme.iconBg} rounded-xl flex items-center justify-center mx-auto mb-3`}>
                            <preset.icon className={`w-6 h-6 ${colorScheme.iconText}`} />
                          </div>
                          <div className="text-lg font-bold text-gray-900 mb-2">{preset.label}</div>
                          <div className="text-sm text-gray-600">{preset.desc}</div>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Clip Duration */}
                <div>
                  <label className="block text-lg font-semibold text-gray-700 mb-4">
                    Preferred Clip Duration
                  </label>
                  <select
                    value={clipDuration}
                    onChange={(e) => setClipDuration(e.target.value)}
                    className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300 text-lg"
                  >
                    <option value="15-30">15-30 seconds</option>
                    <option value="30-60">30-60 seconds</option>
                    <option value="60-90">60-90 seconds</option>
                    <option value="custom">Custom Range</option>
                  </select>
                </div>

                {/* Output Format */}
                <div>
                  <label className="block text-lg font-semibold text-gray-700 mb-4">
                    Output Format
                  </label>
                  <div className="flex flex-wrap gap-4">
                    {['mp4', 'mov', 'webm'].map((format) => (
                      <button
                        key={format}
                        onClick={() => setOutputFormat(format)}
                        className={`px-6 py-3 rounded-xl border-2 transition-all duration-300 font-semibold ${
                          outputFormat === format
                            ? 'border-blue-500 bg-gradient-to-r from-blue-50 to-orange-50 text-blue-700 shadow-lg'
                            : 'border-gray-200 hover:border-gray-300 text-gray-700 hover:shadow-lg'
                        }`}
                      >
                        {format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Features Preview */}
          <div className="space-y-6">
            <div className="bg-white rounded-2xl shadow-xl border border-blue-100 p-8">
              <div className="flex items-center mb-6">
                <div className="bg-gradient-to-r from-green-100 to-green-200 p-3 rounded-xl mr-4">
                  <Sparkles className="w-6 h-6 text-green-600" />
                </div>
                <h3 className="text-2xl font-bold text-gray-900">
                  What You'll Get
                </h3>
              </div>
              
              <div className="space-y-6">
                <div className="flex items-start">
                  <div className="w-12 h-12 bg-gradient-to-r from-green-100 to-green-200 rounded-xl flex items-center justify-center mr-4 mt-1">
                    <Zap className="w-6 h-6 text-green-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900 mb-2">AI-Powered Analysis</div>
                    <div className="text-gray-600">Advanced algorithms identify the most engaging moments in your content</div>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-12 h-12 bg-gradient-to-r from-blue-100 to-blue-200 rounded-xl flex items-center justify-center mr-4 mt-1">
                    <Play className="w-6 h-6 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900 mb-2">Multiple Clips</div>
                    <div className="text-gray-600">Generate 3-10 optimized clips from your content automatically</div>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-12 h-12 bg-gradient-to-r from-orange-100 to-orange-200 rounded-xl flex items-center justify-center mr-4 mt-1">
                    <Clock className="w-6 h-6 text-orange-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900 mb-2">Fast Processing</div>
                    <div className="text-gray-600">Results ready in 2-5 minutes depending on video length</div>
                  </div>
                </div>
                
                <div className="flex items-start">
                  <div className="w-12 h-12 bg-gradient-to-r from-purple-100 to-purple-200 rounded-xl flex items-center justify-center mr-4 mt-1">
                    <TrendingUp className="w-6 h-6 text-purple-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-gray-900 mb-2">Virality Score</div>
                    <div className="text-gray-600">Each clip gets a predicted engagement score to help you choose the best ones</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-r from-blue-50 to-orange-50 rounded-2xl p-8 border-2 border-blue-200">
              <div className="flex items-center mb-4">
                <div className="bg-gradient-to-r from-yellow-100 to-yellow-200 p-2 rounded-lg mr-3">
                  <Star className="w-5 h-5 text-yellow-600" />
                </div>
                <h4 className="text-xl font-bold text-gray-900">💡 Pro Tips</h4>
              </div>
              <div className="space-y-3 text-gray-700">
                <div className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-green-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>Upload videos with clear audio and good lighting</span>
                </div>
                <div className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-green-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>Educational and how-to content performs exceptionally well</span>
                </div>
                <div className="flex items-start">
                  <CheckCircle className="w-5 h-5 text-green-600 mr-2 mt-0.5 flex-shrink-0" />
                  <span>Longer videos (10+ minutes) typically yield more clips</span>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-r from-purple-50 to-blue-50 rounded-2xl p-6 border-2 border-purple-200">
              <div className="text-center">
                <div className="w-16 h-16 bg-gradient-to-r from-purple-100 to-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Award className="w-8 h-8 text-purple-600" />
                </div>
                <h4 className="text-lg font-bold text-gray-900 mb-2">Premium Features</h4>
                <p className="text-sm text-gray-600 mb-4">
                  Unlock advanced AI analysis, custom branding, and priority processing
                </p>
                <button className="bg-gradient-to-r from-purple-600 to-blue-600 text-white px-6 py-2 rounded-xl font-semibold hover:shadow-lg transition-all duration-300">
                  Upgrade Now
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Upload