import React from 'react'
import { Loader2 } from 'lucide-react'

interface LoadingStateProps {
  message?: string
  size?: 'sm' | 'md' | 'lg'
  fullScreen?: boolean
  className?: string
}

const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading...',
  size = 'md',
  fullScreen = false,
  className = ''
}) => {
  const getSpinnerSize = () => {
    switch (size) {
      case 'sm':
        return 'w-4 h-4'
      case 'lg':
        return 'w-12 h-12'
      default:
        return 'w-8 h-8'
    }
  }

  const getTextSize = () => {
    switch (size) {
      case 'sm':
        return 'text-sm'
      case 'lg':
        return 'text-lg'
      default:
        return 'text-base'
    }
  }

  const containerClasses = fullScreen
    ? 'min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center'
    : 'flex items-center justify-center p-8'

  return (
    <div className={`${containerClasses} ${className}`}>
      <div className="text-center fade-in">
        <Loader2 className={`${getSpinnerSize()} animate-spin text-blue-600 mx-auto mb-4`} />
        <p className={`text-gray-600 ${getTextSize()}`}>{message}</p>
      </div>
    </div>
  )
}

export default LoadingState