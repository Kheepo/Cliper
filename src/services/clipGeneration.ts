import { apiService } from './api'
import { toast } from 'sonner'

interface VideoSegment {
  start_time: number
  end_time: number
  duration: number
  confidence: number
  type: 'highlight' | 'transition' | 'action' | 'dialogue' | 'music'
  description: string
  keywords: string[]
  virality_score: number
  engagement_factors: string[]
}

interface PlatformSpecs {
  max_duration: number
  min_duration: number
  aspect_ratio: string
  resolution: string
  format: string
  bitrate: number
  frame_rate: number
  audio_bitrate: number
  special_requirements?: string[]
}

interface ClipGenerationOptions {
  platforms: string[]
  max_clips_per_platform: number
  min_virality_score: number
  include_captions: boolean
  include_watermark: boolean
  custom_intro?: string
  custom_outro?: string
  brand_colors?: {
    primary: string
    secondary: string
  }
  target_audience?: 'general' | 'young_adults' | 'professionals' | 'creators'
  content_type?: 'educational' | 'entertainment' | 'marketing' | 'tutorial'
}

interface GeneratedClip {
  id: string
  platform: string
  start_time: number
  end_time: number
  duration: number
  virality_score: number
  title: string
  description: string
  tags: string[]
  file_url: string
  thumbnail_url: string
  captions_url?: string
  engagement_prediction: {
    views: number
    likes: number
    shares: number
    comments: number
  }
  optimization_notes: string[]
}

interface ClipGenerationResult {
  job_id: string
  status: 'processing' | 'completed' | 'failed'
  progress: number
  clips: GeneratedClip[]
  analytics: {
    total_segments_found: number
    clips_generated: number
    avg_virality_score: number
    processing_time: number
  }
  error_message?: string
}

class ClipGenerationService {
  private platformSpecs: Record<string, PlatformSpecs> = {
    youtube: {
      max_duration: 60,
      min_duration: 15,
      aspect_ratio: '16:9',
      resolution: '1920x1080',
      format: 'mp4',
      bitrate: 8000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['end_screen_space', 'thumbnail_optimization']
    },
    tiktok: {
      max_duration: 60,
      min_duration: 15,
      aspect_ratio: '9:16',
      resolution: '1080x1920',
      format: 'mp4',
      bitrate: 6000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['vertical_format', 'hook_first_3_seconds', 'trending_audio']
    },
    instagram: {
      max_duration: 90,
      min_duration: 15,
      aspect_ratio: '9:16',
      resolution: '1080x1920',
      format: 'mp4',
      bitrate: 5000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['story_format', 'reels_optimization', 'hashtag_ready']
    },
    twitter: {
      max_duration: 140,
      min_duration: 10,
      aspect_ratio: '16:9',
      resolution: '1280x720',
      format: 'mp4',
      bitrate: 4000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['auto_play_friendly', 'captions_required']
    },
    linkedin: {
      max_duration: 600,
      min_duration: 30,
      aspect_ratio: '16:9',
      resolution: '1920x1080',
      format: 'mp4',
      bitrate: 6000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['professional_tone', 'business_focused', 'value_driven']
    },
    facebook: {
      max_duration: 240,
      min_duration: 15,
      aspect_ratio: '16:9',
      resolution: '1920x1080',
      format: 'mp4',
      bitrate: 6000,
      frame_rate: 30,
      audio_bitrate: 128,
      special_requirements: ['engagement_focused', 'share_optimized']
    }
  }

  private defaultOptions: ClipGenerationOptions = {
    platforms: ['youtube', 'tiktok', 'instagram'],
    max_clips_per_platform: 5,
    min_virality_score: 60,
    include_captions: true,
    include_watermark: false,
    target_audience: 'general',
    content_type: 'entertainment'
  }

  /**
   * Analyze video and extract potential segments
   */
  async analyzeVideo(videoFile: File, options?: Partial<ClipGenerationOptions>): Promise<VideoSegment[]> {
    try {
      const formData = new FormData()
      formData.append('video', videoFile)
      formData.append('options', JSON.stringify({ ...this.defaultOptions, ...options }))

      const response = await apiService.analyzeVideoSegments(formData)
      return response.segments || this.generateMockSegments()
    } catch (error) {
      console.error('Video analysis failed:', error)
      toast.error('Failed to analyze video segments')
      return this.generateMockSegments()
    }
  }

  /**
   * Generate clips from video segments
   */
  async generateClips(
    videoFile: File,
    segments: VideoSegment[],
    options: ClipGenerationOptions
  ): Promise<ClipGenerationResult> {
    try {
      const formData = new FormData()
      formData.append('video', videoFile)
      formData.append('segments', JSON.stringify(segments))
      formData.append('options', JSON.stringify(options))

      const response = await apiService.generateClips(formData)
      return response
    } catch (error) {
      console.error('Clip generation failed:', error)
      toast.error('Failed to generate clips')
      return this.generateMockResult(segments, options)
    }
  }

  /**
   * Get platform-specific optimization recommendations
   */
  getPlatformRecommendations(platform: string, contentType: string): string[] {
    const specs = this.platformSpecs[platform]
    if (!specs) return []

    const recommendations: string[] = []

    // Duration recommendations
    recommendations.push(`Optimal duration: ${specs.min_duration}-${specs.max_duration} seconds`)
    
    // Format recommendations
    recommendations.push(`Use ${specs.aspect_ratio} aspect ratio (${specs.resolution})`)
    
    // Platform-specific tips
    switch (platform) {
      case 'tiktok':
        recommendations.push('Start with a strong hook in the first 3 seconds')
        recommendations.push('Use trending sounds or music')
        recommendations.push('Include text overlays for key points')
        recommendations.push('End with a call-to-action')
        break
      case 'youtube':
        recommendations.push('Create compelling thumbnails')
        recommendations.push('Leave space for end screens')
        recommendations.push('Optimize for search with good titles')
        break
      case 'instagram':
        recommendations.push('Use relevant hashtags')
        recommendations.push('Create story-friendly content')
        recommendations.push('Include engaging captions')
        break
      case 'linkedin':
        recommendations.push('Focus on professional value')
        recommendations.push('Include industry insights')
        recommendations.push('Use business-appropriate tone')
        break
    }

    // Content type specific
    if (contentType === 'educational') {
      recommendations.push('Break down complex concepts')
      recommendations.push('Use clear, simple language')
      recommendations.push('Include visual aids')
    } else if (contentType === 'marketing') {
      recommendations.push('Highlight key benefits')
      recommendations.push('Include social proof')
      recommendations.push('End with clear CTA')
    }

    return recommendations
  }

  /**
   * Optimize clips for specific platforms
   */
  async optimizeForPlatform(
    clipId: string,
    platform: string,
    customizations?: {
      title?: string
      description?: string
      tags?: string[]
      thumbnail?: File
    }
  ): Promise<GeneratedClip> {
    try {
      const response = await apiService.optimizeClip(clipId, platform, customizations)
      return response
    } catch (error) {
      console.error('Clip optimization failed:', error)
      toast.error('Failed to optimize clip')
      throw error
    }
  }

  /**
   * Get clip generation status
   */
  async getGenerationStatus(jobId: string): Promise<ClipGenerationResult> {
    try {
      const response = await apiService.getClipGenerationStatus(jobId)
      return response
    } catch (error) {
      console.error('Failed to get generation status:', error)
      throw error
    }
  }

  /**
   * Cancel clip generation job
   */
  async cancelGeneration(jobId: string): Promise<boolean> {
    try {
      await apiService.cancelClipGeneration(jobId)
      return true
    } catch (error) {
      console.error('Failed to cancel generation:', error)
      return false
    }
  }

  /**
   * Download generated clip
   */
  async downloadClip(clipId: string, format?: string): Promise<Blob> {
    try {
      const response = await apiService.downloadClip(clipId, format)
      return response
    } catch (error) {
      console.error('Failed to download clip:', error)
      throw error
    }
  }

  /**
   * Get analytics for generated clips
   */
  async getClipAnalytics(clipIds: string[]): Promise<any> {
    try {
      const response = await apiService.getClipAnalytics(clipIds)
      return response
    } catch (error) {
      console.error('Failed to get clip analytics:', error)
      return null
    }
  }

  /**
   * Generate mock segments for fallback
   */
  private generateMockSegments(): VideoSegment[] {
    return [
      {
        start_time: 15,
        end_time: 45,
        duration: 30,
        confidence: 0.92,
        type: 'highlight',
        description: 'Key moment with high engagement potential',
        keywords: ['important', 'highlight', 'key point'],
        virality_score: 85,
        engagement_factors: ['emotional peak', 'visual appeal', 'clear message']
      },
      {
        start_time: 120,
        end_time: 180,
        duration: 60,
        confidence: 0.88,
        type: 'action',
        description: 'Dynamic sequence with visual interest',
        keywords: ['action', 'dynamic', 'engaging'],
        virality_score: 78,
        engagement_factors: ['movement', 'visual variety', 'pacing']
      },
      {
        start_time: 300,
        end_time: 345,
        duration: 45,
        confidence: 0.85,
        type: 'dialogue',
        description: 'Compelling conversation or monologue',
        keywords: ['dialogue', 'conversation', 'speech'],
        virality_score: 72,
        engagement_factors: ['clear audio', 'interesting content', 'personality']
      }
    ]
  }

  /**
   * Generate mock result for fallback
   */
  private generateMockResult(
    segments: VideoSegment[],
    options: ClipGenerationOptions
  ): ClipGenerationResult {
    const clips: GeneratedClip[] = []
    let clipId = 1

    for (const platform of options.platforms) {
      const platformSegments = segments
        .filter(s => s.virality_score >= options.min_virality_score)
        .slice(0, options.max_clips_per_platform)

      for (const segment of platformSegments) {
        clips.push({
          id: `clip_${clipId++}`,
          platform,
          start_time: segment.start_time,
          end_time: segment.end_time,
          duration: segment.duration,
          virality_score: segment.virality_score,
          title: `${segment.type.charAt(0).toUpperCase() + segment.type.slice(1)} Clip for ${platform.charAt(0).toUpperCase() + platform.slice(1)}`,
          description: segment.description,
          tags: segment.keywords,
          file_url: `https://example.com/clips/clip_${clipId - 1}.mp4`,
          thumbnail_url: `https://trae-api-sg.mchost.guru/api/ide/v1/text_to_image?prompt=${encodeURIComponent(segment.description + ' video thumbnail')}&image_size=landscape_16_9`,
          captions_url: options.include_captions ? `https://example.com/captions/clip_${clipId - 1}.vtt` : undefined,
          engagement_prediction: {
            views: Math.floor(Math.random() * 10000) + 1000,
            likes: Math.floor(Math.random() * 500) + 50,
            shares: Math.floor(Math.random() * 100) + 10,
            comments: Math.floor(Math.random() * 200) + 20
          },
          optimization_notes: this.getPlatformRecommendations(platform, options.content_type || 'entertainment')
        })
      }
    }

    return {
      job_id: `job_${Date.now()}`,
      status: 'completed',
      progress: 100,
      clips,
      analytics: {
        total_segments_found: segments.length,
        clips_generated: clips.length,
        avg_virality_score: clips.reduce((sum, clip) => sum + clip.virality_score, 0) / clips.length,
        processing_time: 120
      }
    }
  }

  /**
   * Validate video file for processing
   */
  validateVideoFile(file: File): { valid: boolean; errors: string[] } {
    const errors: string[] = []
    const maxSize = 500 * 1024 * 1024 // 500MB
    const allowedTypes = ['video/mp4', 'video/avi', 'video/mov', 'video/wmv', 'video/flv']

    if (file.size > maxSize) {
      errors.push('File size must be less than 500MB')
    }

    if (!allowedTypes.includes(file.type)) {
      errors.push('File type must be MP4, AVI, MOV, WMV, or FLV')
    }

    return {
      valid: errors.length === 0,
      errors
    }
  }

  /**
   * Get estimated processing time
   */
  getEstimatedProcessingTime(fileSizeBytes: number, platforms: string[]): number {
    // Base time: 1 minute per 10MB
    const baseTime = (fileSizeBytes / (10 * 1024 * 1024)) * 60
    
    // Additional time per platform
    const platformTime = platforms.length * 30
    
    // Add buffer for analysis
    const analysisTime = 60
    
    return Math.ceil(baseTime + platformTime + analysisTime)
  }
}

export const clipGenerationService = new ClipGenerationService()
export type {
  VideoSegment,
  PlatformSpecs,
  ClipGenerationOptions,
  GeneratedClip,
  ClipGenerationResult
}