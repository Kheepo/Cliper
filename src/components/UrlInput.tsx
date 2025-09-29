import { useState } from 'react'
import { Link as LinkIcon, Play } from 'lucide-react'
import { clsx } from 'clsx'
import { apiService } from '../services/api'

interface UrlInputProps {
  onUrlSubmit: (jobId: string) => void
  disabled?: boolean
}

export default function UrlInput({ onUrlSubmit, disabled }: UrlInputProps) {
  const [url, setUrl] = useState('')
  const [isValid, setIsValid] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  const validateUrl = (url: string) => {
    if (!url) return true
    
    try {
      const urlObj = new URL(url)
      const validDomains = [
        'youtube.com',
        'youtu.be',
        'vimeo.com',
        'tiktok.com',
        'instagram.com',
        'twitter.com',
        'x.com'
      ]
      
      return validDomains.some(domain => 
        urlObj.hostname.includes(domain)
      ) || urlObj.pathname.match(/\.(mp4|mov|avi|mkv|webm)$/i)
    } catch {
      return false
    }
  }

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newUrl = e.target.value
    setUrl(newUrl)
    setIsValid(validateUrl(newUrl) as boolean)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!url.trim()) {
      setIsValid(false)
      setError('Please enter a URL')
      return
    }
    
    if (!validateUrl(url)) {
      setIsValid(false)
      setError('Please enter a valid video URL from supported platforms')
      return
    }
    
    setIsProcessing(true)
    setError(null)
    
    try {
      // Process URL and get job ID
      const response = await apiService.processUrl(url.trim())
      onUrlSubmit(response.job_id)
    } catch (error) {
      console.error('URL processing failed:', error)
      setError(error instanceof Error ? error.message : 'Failed to process URL. Please try again.')
    } finally {
      setIsProcessing(false)
    }
  }

  const getSupportedPlatforms = () => [
    { name: 'YouTube', icon: '🎥' },
    { name: 'TikTok', icon: '🎵' },
    { name: 'Vimeo', icon: '📹' },
    { name: 'Instagram', icon: '📸' },
    { name: 'Twitter/X', icon: '🐦' },
  ]

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <LinkIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="url"
            value={url}
            onChange={handleUrlChange}
            placeholder="https://youtube.com/watch?v=..."
            className={clsx(
              'block w-full pl-10 pr-3 py-3 border rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 sm:text-sm',
              isValid
                ? 'border-gray-300 focus:ring-blue-500 focus:border-blue-500'
                : 'border-red-300 focus:ring-red-500 focus:border-red-500'
            )}
            disabled={disabled}
          />
        </div>
        
        {error && (
          <p className="text-sm text-red-600">
            {error}
          </p>
        )}
        
        <button
          type="submit"
          disabled={disabled || isProcessing || !url.trim() || !isValid}
          className={clsx(
            'w-full flex items-center justify-center px-4 py-3 border border-transparent rounded-md shadow-sm text-sm font-medium transition-colors',
            disabled || isProcessing || !url.trim() || !isValid
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
          )}
        >
          <Play className="w-4 h-4 mr-2" />
          {disabled || isProcessing ? 'Processing...' : 'Process URL'}
        </button>
      </form>
      
      {/* Supported platforms */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-900 mb-2">Supported Platforms:</h4>
        <div className="flex flex-wrap gap-2">
          {getSupportedPlatforms().map((platform) => (
            <span
              key={platform.name}
              className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-white text-gray-700 border"
            >
              <span className="mr-1">{platform.icon}</span>
              {platform.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}