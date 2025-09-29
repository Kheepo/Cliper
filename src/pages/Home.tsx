import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Play, Upload, Zap, TrendingUp, Clock, Star, Video, BarChart3, Sparkles } from 'lucide-react'
import FileUpload from '../components/FileUpload'
import UrlInput from '../components/UrlInput'
import ToastContainer from '../components/ToastContainer'
import { apiService } from '../services/api'
import { useToast } from '../hooks/useToast'

const Home = () => {
  const navigate = useNavigate()
  const { toasts, removeToast, success, error, info } = useToast();
  const [uploadMethod, setUploadMethod] = useState<'file' | 'url'>('file');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingJobId, setProcessingJobId] = useState<string | null>(null);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [jobStatus, setJobStatus] = useState<string>('');

  const features = [
    {
      icon: Zap,
      title: 'AI-Powered Analysis',
      description: 'Advanced algorithms identify the most engaging moments in your content',
      gradient: 'from-blue-500 to-blue-600'
    },
    {
      icon: TrendingUp,
      title: 'Virality Scoring',
      description: 'Get precise scores predicting how viral each clip will be',
      gradient: 'from-orange-500 to-orange-600'
    },
    {
      icon: Clock,
      title: 'Fast Processing',
      description: 'Generate multiple clips in minutes, not hours',
      gradient: 'from-blue-600 to-orange-500'
    },
    {
      icon: Star,
      title: 'Platform Optimization',
      description: 'Clips optimized for TikTok, Instagram, YouTube Shorts, and more',
      gradient: 'from-orange-600 to-blue-500'
    }
  ]

  const handleUploadComplete = (jobId: string) => {
    setProcessingJobId(jobId);
    setIsProcessing(true);
    setUploadComplete(true);
    setJobStatus('Processing video...');
    success('Upload successful! Processing your video...');
    
    // Start polling job status
    pollJobStatus(jobId);
  };

  const pollJobStatus = async (jobId: string) => {
    try {
      const status = await apiService.getJobStatus(jobId);
      setJobStatus(status.status === 'completed' ? 'Processing complete!' : 
                  status.status === 'failed' ? 'Processing failed' : 
                  'Processing video...');
      
      if (status.status === 'completed') {
        success('Video processing complete! Redirecting to results...');
        setTimeout(() => {
          navigate(`/results/${jobId}`);
        }, 2000); // Show success message for 2 seconds before redirect
      } else if (status.status === 'failed') {
        error('Video processing failed. Please try again.');
        setIsProcessing(false);
      } else {
        // Continue polling every 3 seconds
        setTimeout(() => pollJobStatus(jobId), 3000);
      }
    } catch (error) {
      console.error('Error polling job status:', error);
      error('Error checking processing status');
      setJobStatus('Error checking status');
      setIsProcessing(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <ToastContainer toasts={toasts} onRemoveToast={removeToast} />
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/5 to-orange-500/5"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div className="text-center">
            <div className="flex items-center justify-center mb-6">
              <div className="bg-gradient-to-r from-blue-600 to-orange-500 p-4 rounded-2xl shadow-xl">
                <Video className="w-12 h-12 text-white" />
              </div>
            </div>
            <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
              Turn Your Videos Into
              <span className="block bg-gradient-to-r from-blue-600 to-orange-500 bg-clip-text text-transparent">
                Viral Clips
              </span>
            </h1>
            <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto leading-relaxed">
              Upload your long-form content and let our AI identify the most engaging moments. 
              Create viral clips optimized for every social platform in minutes.
            </p>
            
            <div className="flex flex-col sm:flex-row gap-4 justify-center mb-12">
              <button 
                onClick={() => navigate('/upload')}
                className="bg-gradient-to-r from-blue-600 to-orange-500 text-white px-8 py-4 rounded-xl font-semibold text-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 flex items-center justify-center"
              >
                <Upload className="w-5 h-5 mr-2" />
                Start Creating Clips
              </button>
              <button 
                onClick={() => navigate('/dashboard')}
                className="border-2 border-blue-600 text-blue-600 px-8 py-4 rounded-xl font-semibold text-lg hover:bg-blue-50 hover:shadow-lg transition-all duration-300 flex items-center justify-center"
              >
                <BarChart3 className="w-5 h-5 mr-2" />
                View Dashboard
              </button>
            </div>
            
            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-2xl mx-auto">
              <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 shadow-lg">
                <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-orange-500 bg-clip-text text-transparent">10M+</div>
                <div className="text-gray-600 font-medium">Clips Generated</div>
              </div>
              <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 shadow-lg">
                <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-orange-500 bg-clip-text text-transparent">98%</div>
                <div className="text-gray-600 font-medium">Accuracy Rate</div>
              </div>
              <div className="bg-white/80 backdrop-blur-sm rounded-xl p-6 shadow-lg">
                <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-orange-500 bg-clip-text text-transparent">50K+</div>
                <div className="text-gray-600 font-medium">Happy Creators</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Section */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-4">
            <Sparkles className="w-8 h-8 text-orange-500 mr-2" />
            <h2 className="text-3xl font-bold text-gray-900">
              Get Started in Seconds
            </h2>
          </div>
          <p className="text-lg text-gray-600">
            Upload a video file or paste a URL to begin your viral journey
          </p>
        </div>

        <div className="bg-white rounded-lg shadow-lg p-8">
          {!uploadComplete ? (
            <>
              <div className="flex justify-center mb-6">
                <div className="flex bg-gray-100 rounded-lg p-1">
                  <button
                    onClick={() => setUploadMethod('file')}
                    className={`px-4 py-2 rounded-md transition-colors ${
                      uploadMethod === 'file'
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    Upload File
                  </button>
                  <button
                    onClick={() => setUploadMethod('url')}
                    className={`px-4 py-2 rounded-md transition-colors ${
                      uploadMethod === 'url'
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-600 hover:text-gray-800'
                    }`}
                  >
                    YouTube URL
                  </button>
                </div>
              </div>

              {uploadMethod === 'file' ? (
                <FileUpload onFileSelect={handleUploadComplete} />
              ) : (
                <UrlInput onUrlSubmit={handleUploadComplete} />
              )}
            </>
          ) : (
            <div className="text-center py-12">
              <div className="mb-6">
                {isProcessing ? (
                  <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
                ) : (
                  <div className="h-16 w-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="h-8 w-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                )}
              </div>
              <h3 className="text-xl font-semibold text-gray-900 mb-2">
                {isProcessing ? 'Processing Your Video' : 'Processing Complete!'}
              </h3>
              <p className="text-gray-600 mb-4">{jobStatus}</p>
              {!isProcessing && (
                <button
                  onClick={() => {
                    setUploadComplete(false);
                    setIsProcessing(false);
                    setProcessingJobId(null);
                    setJobStatus('');
                  }}
                  className="text-blue-600 hover:text-blue-800 font-medium"
                >
                  Upload Another Video
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              Why Choose VideoClipper?
            </h2>
            <p className="text-xl text-gray-600 max-w-3xl mx-auto leading-relaxed">
              Our AI-powered platform makes it easy to create engaging short-form content 
              that drives views, engagement, and growth.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {features.map((feature, index) => {
              const Icon = feature.icon
              return (
                <div key={index} className="text-center group hover:transform hover:-translate-y-2 transition-all duration-300">
                  <div className={`bg-gradient-to-r ${feature.gradient} w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-lg group-hover:shadow-xl`}>
                    <Icon className="w-8 h-8 text-white" />
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-gray-600 leading-relaxed">
                    {feature.description}
                  </p>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* How It Works Section */}
      <div className="bg-gradient-to-br from-slate-50 to-blue-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              How It Works
            </h2>
            <p className="text-xl text-gray-600">
              From upload to viral clips in just a few simple steps
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              {
                step: '1',
                title: 'Upload Your Video',
                description: 'Upload your long-form content or paste a URL from YouTube, TikTok, or other platforms',
                color: 'from-blue-600 to-blue-700'
              },
              {
                step: '2',
                title: 'AI Analysis',
                description: 'Our AI analyzes your content to identify the most engaging moments and viral potential',
                color: 'from-blue-600 to-orange-500'
              },
              {
                step: '3',
                title: 'Get Your Clips',
                description: 'Download optimized clips with virality scores and platform-specific formatting',
                color: 'from-orange-500 to-orange-600'
              }
            ].map((item, index) => (
              <div key={index} className="text-center group">
                <div className="bg-white rounded-2xl p-8 shadow-lg hover:shadow-xl transition-all duration-300 group-hover:transform group-hover:-translate-y-1">
                  <div className={`bg-gradient-to-r ${item.color} w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg`}>
                    <span className="text-white font-bold text-lg">{item.step}</span>
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 mb-2">
                    {item.title}
                  </h3>
                  <p className="text-gray-600 leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="bg-gradient-to-r from-blue-600 to-orange-500 py-16">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Go Viral?
          </h2>
          <p className="text-xl text-blue-100 mb-8">
            Join thousands of creators who are already using VideoClipper to grow their audience
          </p>
          <button 
            onClick={() => navigate('/upload')}
            className="bg-white text-blue-600 px-8 py-4 rounded-xl font-semibold text-lg hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1 flex items-center justify-center mx-auto"
          >
            <Upload className="w-5 h-5 mr-2" />
            Start Creating Now
          </button>
        </div>
      </div>
    </div>
  )
}

export default Home