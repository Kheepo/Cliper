import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import ClipGenerationModal from '../ClipGenerationModal'

// Mock external dependencies
vi.mock('../../services/apiService', () => ({
  default: {
    generateClip: vi.fn(),
  },
}))

vi.mock('../../services/webSocketService', () => ({
  default: {
    connect: vi.fn(),
    disconnect: vi.fn(),
    send: vi.fn(),
  },
}))

// Mock Lucide React icons
vi.mock('lucide-react', () => ({
  Play: () => <div data-testid="play-icon" />,
  Download: () => <div data-testid="download-icon" />,
  AlertCircle: () => <div data-testid="alert-icon" />,
  X: () => <div data-testid="x-icon" />,
  Settings: () => <div data-testid="settings-icon" />,
  Clock: () => <div data-testid="clock-icon" />,
  Video: () => <div data-testid="video-icon" />,
}))

describe('ClipGenerationModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    segment: {
      id: 'test-segment',
      startTime: 0,
      endTime: 30,
      title: 'Test Segment',
      description: 'Test Description',
    },
    jobId: 'test-job-123',
    onClipGenerated: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Modal Rendering', () => {
    it('renders modal when open', () => {
      render(<ClipGenerationModal {...defaultProps} />)
      
      expect(screen.getByText('Generate Clip')).toBeInTheDocument()
    })

    it('does not render when closed', () => {
      render(<ClipGenerationModal {...defaultProps} isOpen={false} />)
      
      expect(screen.queryByText('Generate Clip')).not.toBeInTheDocument()
    })
  })

  describe('Platform Selection', () => {
    it('renders platform selection options', () => {
      render(<ClipGenerationModal {...defaultProps} />)
      
      // Check for platform tab
      expect(screen.getByText('Platform')).toBeInTheDocument()
    })
  })

  describe('Basic Functionality', () => {
    it('renders basic UI elements', () => {
      render(<ClipGenerationModal {...defaultProps} />)
      
      // Check for basic tabs
      expect(screen.getByText('Basic')).toBeInTheDocument()
      expect(screen.getByText('Advanced')).toBeInTheDocument()
    })

    it('renders generate button', () => {
      render(<ClipGenerationModal {...defaultProps} />)
      
      expect(screen.getByText('Generate Clip')).toBeInTheDocument()
    })

    it('renders cancel button', () => {
      render(<ClipGenerationModal {...defaultProps} />)
      
      expect(screen.getByText('Cancel')).toBeInTheDocument()
    })
  })
})