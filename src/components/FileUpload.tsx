import React, { useState, useRef, useEffect } from 'react'
import { Upload, X, FileVideo, AlertCircle, CheckCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { apiService } from '../services/api'
import { resumableUploadService, UploadSession } from '../services/resumableUpload'
import { resourceMonitor } from '../services/resourceMonitor'
import { ErrorCategorizationService, ErrorCategory, ErrorSeverity } from '../services/errorCategorization'
import { retryService } from '../services/retryService'
import { errorCategorizationService } from '../services/errorCategorizationService'

interface FileWithProgress {
  id: string
  file: File
  progress: number
  status: 'pending' | 'uploading' | 'completed' | 'error' | 'paused'
  error?: string
  uploadSpeed?: number
  estimatedTimeRemaining?: number
}

interface FileUploadProps {
  onFileSelect: (jobId: string) => void
  onUploadStart?: () => void
  onUploadProgress?: (progress: number) => void
  onUploadError?: (error: string) => void
  disabled?: boolean
  uploadProgress?: number
}

export default function FileUpload({ onFileSelect, onUploadStart, onUploadProgress, onUploadError, disabled, uploadProgress }: FileUploadProps) {
  const [isDragOver, setIsDragOver] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'paused' | 'completed' | 'error'>('idle')
  const [errorDetails, setErrorDetails] = useState<string | null>(null)
  const [canResume, setCanResume] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // Use the singleton instance from the service module
  const errorCategorizationRef = useRef<ErrorCategorizationService | null>(null)

  useEffect(() => {
    // Initialize services
    errorCategorizationRef.current = new ErrorCategorizationService()

    return () => {
      // Cleanup on unmount
      resourceMonitor.stopMonitoring()
    }
  }, [])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (!disabled) {
      setIsDragOver(true)
    }
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    
    if (disabled) return

    const files = Array.from(e.dataTransfer.files)
    const videoFile = files.find(file => file.type.startsWith('video/'))
    
    if (videoFile) {
      handleFileSelection(videoFile)
    }
  }

  const handleFileSelection = (file: File) => {
    // Validate file size (2GB limit)
    const maxSize = 2 * 1024 * 1024 * 1024; // 2GB
    if (file.size > maxSize) {
      const errorMessage = `File size (${(file.size / (1024 * 1024 * 1024)).toFixed(2)}GB) exceeds maximum allowed size of 2GB`;
      setErrorDetails(errorMessage);
      onUploadError?.(errorMessage);
      return;
    }
    
    // Validate file type
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv', 'video/webm', 'video/mkv'];
    if (!allowedTypes.includes(file.type)) {
      const errorMessage = `Unsupported file type: ${file.type}. Please upload a video file.`;
      setErrorDetails(errorMessage);
      onUploadError?.(errorMessage);
      return;
    }

    setSelectedFile(file)
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      handleFileSelection(file)
    }
  }

  const handleUpload = async (retryCount = 0) => {
    if (!selectedFile || !errorCategorizationRef.current) return

    try {
      setUploadStatus('uploading')
      setErrorDetails(null)
      onUploadStart?.()

      // Check if we can resume an existing upload
      const activeSessions = resumableUploadService.getActiveSessions()
      const existingSession = activeSessions.find(session => session.fileName === selectedFile.name)
      if (existingSession && existingSession.uploadedChunks.size > 0) {
        setCanResume(true)
        console.log(`Found existing upload session. ${existingSession.uploadedChunks.size} chunks already uploaded.`)
        // Show resume option to user
        const progress = Math.round((existingSession.uploadedChunks.size / existingSession.totalChunks) * 100)
        setErrorDetails(`Previous upload found (${progress}% complete). You can resume or start over.`)
        setUploadStatus('error')
        return
      }

      const uploadOperation = async () => {
        // Use resumable upload for files larger than 50MB
        const useResumableUpload = selectedFile.size > 50 * 1024 * 1024;
        
        if (useResumableUpload) {
          // Use resumable upload service for large files
          return await resumableUploadService.uploadFile(
            selectedFile,
            {
              onProgress: (progress) => {
                onUploadProgress?.(progress)
              }
            }
          )
        } else {
          // Use regular upload for smaller files
          return await apiService.uploadVideo(selectedFile, (progress) => {
            onUploadProgress?.(progress)
          })
        }
      }

      const result = await retryService.createUploadRetryWrapper(
        uploadOperation,
        selectedFile.name,
        selectedFile.size
      )

      if (result.success) {
        setUploadStatus('completed')
        onFileSelect(result.data.job_id)
        
        // Clean up successful upload session
        resumableUploadService.clearAllSessions()
      } else {
        setUploadStatus('error')
        const errorMessage = result.error?.message || 'Upload failed'
        setErrorDetails(errorMessage)
        onUploadError?.(errorMessage)
        
        // Check if upload can be resumed later
        if (result.error && (result.error.message.includes('network') || result.error.message.includes('timeout'))) {
          setCanResume(true)
          setErrorDetails(errorMessage + ' You can resume the upload or try again.')
        }
      }
      
    } catch (error) {
      console.error('Upload failed:', error)
      
      // Categorize the error using the new service
      const errorCategory = errorCategorizationService.categorizeError(error)
      
      // Handle retryable errors
      if (errorCategory.retryable) {
        setCanResume(true)
        setErrorDetails(errorCategory.userMessage)
      } else {
        setErrorDetails(errorCategory.userMessage)
      }
      
      setUploadStatus('error')
      onUploadError?.(errorCategory.userMessage)
    }
  }

  const handleRemoveFile = async () => {
    if (selectedFile) {
      // Clean up any existing upload session
      resumableUploadService.clearAllSessions()
    }
    
    setSelectedFile(null)
    setUploadStatus('idle')
    setErrorDetails(null)
    setCanResume(false)
    
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleResumeUpload = async () => {
    if (!selectedFile || !canResume || uploadStatus !== 'error') return
    
    try {
      setUploadStatus('uploading')
      setErrorDetails(null)
      
      // Resume the upload session
      const sessionId = resumableUploadService.generateSessionId(selectedFile)
      resumableUploadService.resumeUpload(sessionId)
      
      await resumableUploadService.uploadFile(
        selectedFile,
        {
          onProgress: (progress) => {
            // Get detailed session info for enhanced progress display
            const sessionDetails = resumableUploadService.getSessionDetails(sessionId)
            onUploadProgress?.(progress)
          }
        }
      )
      
      setUploadStatus('completed')
      setCanResume(false)
    } catch (error) {
       console.error('Resume upload failed:', error)
       const errorCategory = errorCategorizationService.categorizeError(error)
       
       setUploadStatus('error')
       setErrorDetails(errorCategory.userMessage)
       onUploadError?.(errorCategory.userMessage)
     }
  }

  const handlePauseUpload = () => {
    if (!selectedFile || uploadStatus !== 'uploading') return
    
    try {
      const sessionId = resumableUploadService.generateSessionId(selectedFile)
      resumableUploadService.pauseUpload(sessionId)
      setUploadStatus('paused')
      setCanResume(true)
    } catch (error) {
      console.error('Pause upload failed:', error)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <div className="space-y-4">
      {!selectedFile ? (
        <div
          className={clsx(
            'border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer',
            isDragOver && !disabled
              ? 'border-purple-400 bg-purple-50'
              : 'border-gray-300 hover:border-purple-400 hover:bg-purple-50',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
        >
          <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-lg font-medium text-gray-900 mb-2">
            Drop your video here, or click to browse
          </p>
          <p className="text-sm text-gray-500">
            MP4, MOV, AVI up to 2GB
          </p>
          
          <input
            ref={fileInputRef}
            type="file"
            accept="video/*"
            onChange={handleFileInputChange}
            className="hidden"
            disabled={disabled}
          />
        </div>
      ) : (
        <div className="border rounded-lg p-4 bg-gray-50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="relative">
                <FileVideo className="w-8 h-8 text-purple-600" />
                {uploadStatus === 'completed' && (
                  <CheckCircle className="w-4 h-4 text-green-500 absolute -top-1 -right-1 bg-white rounded-full" />
                )}
                {uploadStatus === 'error' && (
                  <AlertCircle className="w-4 h-4 text-red-500 absolute -top-1 -right-1 bg-white rounded-full" />
                )}
              </div>
              <div>
                <p className="font-medium text-gray-900">{selectedFile.name}</p>
                <p className="text-sm text-gray-500">{formatFileSize(selectedFile.size)}</p>
                {uploadStatus === 'error' && errorDetails && (
                  <p className="text-sm text-red-600 mt-1">{errorDetails}</p>
                )}
                {canResume && uploadStatus === 'error' && (
                  <p className="text-sm text-blue-600 mt-1">Upload can be resumed</p>
                )}
              </div>
            </div>
            <button
              onClick={handleRemoveFile}
              className="p-1 hover:bg-gray-200 rounded"
              disabled={disabled || uploadStatus === 'uploading'}
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
          
          <div className="mt-4 space-y-2">
            {uploadStatus === 'uploading' && uploadProgress !== undefined && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span>Uploading...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-purple-600 h-2 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
                
                {/* Enhanced Progress Info */}
                {selectedFile && (
                  <div className="mt-2 text-xs text-gray-500 space-y-1">
                    {(() => {
                      const sessionId = resumableUploadService.generateSessionId(selectedFile)
                      const sessionDetails = resumableUploadService.getSessionDetails(sessionId)
                      
                      if (sessionDetails) {
                        const formatSpeed = (bytesPerSecond: number) => {
                          if (bytesPerSecond < 1024) return `${bytesPerSecond.toFixed(0)} B/s`
                          if (bytesPerSecond < 1024 * 1024) return `${(bytesPerSecond / 1024).toFixed(1)} KB/s`
                          return `${(bytesPerSecond / (1024 * 1024)).toFixed(1)} MB/s`
                        }
                        
                        const formatTime = (seconds: number) => {
                          if (seconds < 60) return `${Math.round(seconds)}s`
                          if (seconds < 3600) return `${Math.round(seconds / 60)}m ${Math.round(seconds % 60)}s`
                          return `${Math.round(seconds / 3600)}h ${Math.round((seconds % 3600) / 60)}m`
                        }
                        
                        return (
                          <>
                            {sessionDetails.uploadSpeed > 0 && (
                              <div>Speed: {formatSpeed(sessionDetails.uploadSpeed)}</div>
                            )}
                            {sessionDetails.estimatedTimeRemaining > 0 && (
                              <div>Time remaining: {formatTime(sessionDetails.estimatedTimeRemaining)}</div>
                            )}
                          </>
                        )
                      }
                      return null
                    })()} 
                  </div>
                )}
              </div>
            )}
            
            <div className="flex space-x-2">
              {uploadStatus === 'idle' || uploadStatus === 'error' ? (
                <button
                  onClick={() => uploadStatus === 'error' && canResume ? handleResumeUpload() : handleUpload()}
                  disabled={disabled}
                  className={clsx(
                    'flex-1 px-4 py-2 rounded-md font-medium transition-colors',
                    disabled
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : uploadStatus === 'error' && canResume
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-purple-600 text-white hover:bg-purple-700'
                  )}
                >
                  {uploadStatus === 'error' && canResume ? 'Resume Upload' : 'Upload & Process'}
                </button>
              ) : uploadStatus === 'uploading' ? (
                <button
                  onClick={() => handlePauseUpload()}
                  className="flex-1 px-4 py-2 rounded-md font-medium bg-yellow-600 text-white hover:bg-yellow-700 transition-colors"
                >
                  Pause Upload
                </button>
              ) : uploadStatus === 'paused' ? (
                <button
                  onClick={() => handleResumeUpload()}
                  className="flex-1 px-4 py-2 rounded-md font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                >
                  Resume Upload
                </button>
              ) : uploadStatus === 'completed' ? (
                <div className="flex-1 px-4 py-2 rounded-md font-medium bg-green-600 text-white text-center">
                  Upload Completed
                </div>
              ) : (
                <div className="flex-1 px-4 py-2 rounded-md font-medium bg-gray-300 text-gray-500 text-center">
                  Processing...
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}