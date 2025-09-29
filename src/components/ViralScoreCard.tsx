import React from 'react'
import { 
  Star, 
  TrendingUp, 
  Heart, 
  MessageCircle, 
  Share2, 
  Eye, 
  Target,
  Award,
  Zap,
  Info,
  CheckCircle,
  AlertTriangle
} from 'lucide-react'

interface ViralFactor {
  factor: string
  score: number
  confidence: number
  explanation: string
}

interface PlatformScore {
  score: number
  confidence?: number
}

interface ViralMoment {
  timestamp: number
  intensity: number
  description: string
  factors: string[]
}

interface ViralAnalysis {
  overall_score: number
  platform_scores: {
    [platform: string]: PlatformScore
  }
  viral_factors: ViralFactor[]
  viral_moments: ViralMoment[]
  insights: string[]
  confidence: number
}

interface ViralScoreCardProps {
  viralAnalysis: ViralAnalysis
  compact?: boolean
  showDetails?: boolean
  className?: string
}

const ViralScoreCard: React.FC<ViralScoreCardProps> = ({
  viralAnalysis,
  compact = false,
  showDetails = true,
  className = ''
}) => {
  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600 bg-green-100 border-green-200'
    if (score >= 6) return 'text-yellow-600 bg-yellow-100 border-yellow-200'
    return 'text-red-600 bg-red-100 border-red-200'
  }

  const getScoreLabel = (score: number) => {
    if (score >= 8) return 'High Viral Potential'
    if (score >= 6) return 'Medium Viral Potential'
    return 'Low Viral Potential'
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.8) return 'text-green-600'
    if (confidence >= 0.6) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.8) return 'High Confidence'
    if (confidence >= 0.6) return 'Medium Confidence'
    return 'Low Confidence'
  }

  const getFactorIcon = (factor: string) => {
    switch (factor.toLowerCase()) {
      case 'engagement':
        return <Heart className="w-4 h-4" />
      case 'shareability':
        return <Share2 className="w-4 h-4" />
      case 'emotional_impact':
        return <Zap className="w-4 h-4" />
      case 'trending_potential':
        return <TrendingUp className="w-4 h-4" />
      case 'audience_retention':
        return <Eye className="w-4 h-4" />
      case 'content_quality':
        return <Award className="w-4 h-4" />
      default:
        return <Star className="w-4 h-4" />
    }
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }

  if (compact) {
    return (
      <div className={`bg-white rounded-lg border p-4 ${className}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className={`px-3 py-1 rounded-full text-sm font-medium border ${
              getScoreColor(viralAnalysis.overall_score)
            }`}>
              {viralAnalysis.overall_score.toFixed(1)}
            </div>
            <div>
              <p className="text-sm font-medium text-gray-900">
                {getScoreLabel(viralAnalysis.overall_score)}
              </p>
              <p className={`text-xs ${getConfidenceColor(viralAnalysis.confidence)}`}>
                {getConfidenceLabel(viralAnalysis.confidence)} ({(viralAnalysis.confidence * 100).toFixed(0)}%)
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-1">
            {viralAnalysis.confidence >= 0.8 ? (
              <CheckCircle className="w-4 h-4 text-green-600" />
            ) : viralAnalysis.confidence >= 0.6 ? (
              <Info className="w-4 h-4 text-yellow-600" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-600" />
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`bg-white rounded-xl shadow-lg border ${className}`}>
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Viral Analysis</h3>
          <div className="flex items-center space-x-2">
            <span className={`px-3 py-1 rounded-full text-sm font-medium border ${
              getScoreColor(viralAnalysis.overall_score)
            }`}>
              {viralAnalysis.overall_score.toFixed(1)}
            </span>
            {viralAnalysis.confidence >= 0.8 ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : viralAnalysis.confidence >= 0.6 ? (
              <Info className="w-5 h-5 text-yellow-600" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-red-600" />
            )}
          </div>
        </div>
        
        <div className="flex items-center justify-between">
          <span className={`px-4 py-2 rounded-lg text-sm font-medium border ${
            getScoreColor(viralAnalysis.overall_score)
          }`}>
            {getScoreLabel(viralAnalysis.overall_score)}
          </span>
          <div className="text-right">
            <p className="text-sm text-gray-600">Analysis Confidence</p>
            <p className={`text-sm font-medium ${getConfidenceColor(viralAnalysis.confidence)}`}>
              {getConfidenceLabel(viralAnalysis.confidence)} ({(viralAnalysis.confidence * 100).toFixed(0)}%)
            </p>
          </div>
        </div>
      </div>

      {/* Platform Scores */}
      <div className="p-6 border-b border-gray-200">
        <h4 className="text-sm font-semibold text-gray-900 mb-4">Platform Optimization</h4>
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(viralAnalysis.platform_scores).map(([platform, scoreData]) => (
            <div key={platform} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
              <div>
                <span className="text-sm font-medium text-gray-900 capitalize">
                  {platform.replace('_', ' ')}
                </span>
                {scoreData.confidence && (
                  <p className={`text-xs ${getConfidenceColor(scoreData.confidence)}`}>
                    {(scoreData.confidence * 100).toFixed(0)}% confidence
                  </p>
                )}
              </div>
              <span className={`px-2 py-1 rounded text-sm font-bold ${
                getScoreColor(scoreData.score)
              }`}>
                {scoreData.score.toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Viral Factors */}
      {showDetails && viralAnalysis.viral_factors.length > 0 && (
        <div className="p-6 border-b border-gray-200">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Viral Factors</h4>
          <div className="space-y-3">
            {viralAnalysis.viral_factors.map((factor, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="flex-shrink-0 p-2 bg-purple-100 rounded-lg">
                  {getFactorIcon(factor.factor)}
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-900 capitalize">
                      {factor.factor.replace('_', ' ')}
                    </span>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        getScoreColor(factor.score)
                      }`}>
                        {factor.score.toFixed(1)}
                      </span>
                      <span className={`text-xs ${getConfidenceColor(factor.confidence)}`}>
                        {(factor.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-600">{factor.explanation}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Viral Moments */}
      {showDetails && viralAnalysis.viral_moments.length > 0 && (
        <div className="p-6 border-b border-gray-200">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">Viral Moments</h4>
          <div className="space-y-3">
            {viralAnalysis.viral_moments.slice(0, 3).map((moment, index) => (
              <div key={index} className="flex items-start space-x-3">
                <div className="flex-shrink-0 p-2 bg-yellow-100 rounded-lg">
                  <Zap className="w-4 h-4 text-yellow-600" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-900">
                      {formatTime(moment.timestamp)}
                    </span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      moment.intensity >= 0.8 ? 'bg-red-100 text-red-600' :
                      moment.intensity >= 0.6 ? 'bg-yellow-100 text-yellow-600' :
                      'bg-green-100 text-green-600'
                    }`}>
                      {(moment.intensity * 100).toFixed(0)}% intensity
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 mb-2">{moment.description}</p>
                  <div className="flex flex-wrap gap-1">
                    {moment.factors.map((factor, factorIndex) => (
                      <span key={factorIndex} className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded">
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Insights */}
      {showDetails && viralAnalysis.insights.length > 0 && (
        <div className="p-6">
          <h4 className="text-sm font-semibold text-gray-900 mb-4">AI Insights</h4>
          <div className="space-y-2">
            {viralAnalysis.insights.map((insight, index) => (
              <div key={index} className="flex items-start space-x-2">
                <div className="flex-shrink-0 w-2 h-2 bg-purple-500 rounded-full mt-2"></div>
                <p className="text-sm text-gray-700">{insight}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ViralScoreCard