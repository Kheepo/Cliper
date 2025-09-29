import React from 'react'
import { AlertCircle, RefreshCw, Home } from 'lucide-react'

interface ErrorStateProps {
  title?: string
  message?: string
  onRetry?: () => void
  onGoHome?: () => void
  showRetry?: boolean
  showGoHome?: boolean
  fullScreen?: boolean
  className?: string
}

const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message = 'An unexpected error occurred. Please try again.',
  onRetry,
  onGoHome,
  showRetry = true,
  showGoHome = false,
  fullScreen = false,
  className = ''
}) => {
  const containerClasses = fullScreen
    ? 'min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center'
    : 'flex items-center justify-center p-8'

  return (
    <div className={`${containerClasses} ${className}`}>
      <div className="text-center max-w-md mx-auto scale-in">
        <div className="bg-red-100 p-4 rounded-full w-16 h-16 mx-auto mb-6 flex items-center justify-center">
          <AlertCircle className="w-8 h-8 text-red-600" />
        </div>
        
        <h2 className="text-xl font-semibold text-gray-900 mb-3">
          {title}
        </h2>
        
        <p className="text-gray-600 mb-6 leading-relaxed">
          {message}
        </p>
        
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          {showRetry && onRetry && (
            <button
              onClick={onRetry}
              className="btn btn-primary inline-flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </button>
          )}
          
          {showGoHome && onGoHome && (
            <button
              onClick={onGoHome}
              className="btn btn-secondary inline-flex items-center gap-2"
            >
              <Home className="w-4 h-4" />
              Go Home
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default ErrorState