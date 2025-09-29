import React from 'react'
import { CheckCircle, Clock, XCircle, AlertCircle, Loader, Pause } from 'lucide-react'

interface StatusBadgeProps {
  status: 'completed' | 'processing' | 'failed' | 'pending' | 'cancelled' | 'paused'
  size?: 'sm' | 'md' | 'lg'
  showIcon?: boolean
  className?: string
}

const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  showIcon = true,
  className = ''
}) => {
  const getStatusConfig = () => {
    switch (status) {
      case 'completed':
        return {
          icon: CheckCircle,
          text: 'Completed',
          classes: 'status-success'
        }
      case 'processing':
        return {
          icon: Loader,
          text: 'Processing',
          classes: 'status-info',
          animate: true
        }
      case 'failed':
        return {
          icon: XCircle,
          text: 'Failed',
          classes: 'status-error'
        }
      case 'pending':
        return {
          icon: Clock,
          text: 'Pending',
          classes: 'status-warning'
        }
      case 'cancelled':
        return {
          icon: XCircle,
          text: 'Cancelled',
          classes: 'bg-gray-100 text-gray-800 border border-gray-200'
        }
      case 'paused':
        return {
          icon: Pause,
          text: 'Paused',
          classes: 'bg-orange-100 text-orange-800 border border-orange-200'
        }
      default:
        return {
          icon: AlertCircle,
          text: 'Unknown',
          classes: 'bg-gray-100 text-gray-800 border border-gray-200'
        }
    }
  }

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'px-2 py-1 text-xs'
      case 'lg':
        return 'px-4 py-2 text-base'
      default:
        return 'px-3 py-1.5 text-sm'
    }
  }

  const getIconSize = () => {
    switch (size) {
      case 'sm':
        return 'w-3 h-3'
      case 'lg':
        return 'w-5 h-5'
      default:
        return 'w-4 h-4'
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  return (
    <span className={`
      inline-flex items-center gap-1.5 rounded-full font-medium
      ${config.classes}
      ${getSizeClasses()}
      ${className}
    `}>
      {showIcon && (
        <Icon className={`
          ${getIconSize()}
          ${config.animate ? 'animate-spin' : ''}
        `} />
      )}
      {config.text}
    </span>
  )
}

export default StatusBadge