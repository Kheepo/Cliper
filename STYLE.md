# Cliper Style Guide

This document defines the coding standards and style guidelines for the Cliper project.

## General Principles

1. **Consistency**: Follow existing patterns in the codebase
2. **Readability**: Code should be self-documenting and easy to understand
3. **Maintainability**: Write code that is easy to modify and extend
4. **Performance**: Consider performance implications of code choices
5. **Security**: Always consider security implications

## Python (Backend)

### Code Formatting
- Use **Black** for code formatting (line length: 88 characters)
- Use **isort** for import sorting
- Use **flake8** for linting
- Use **mypy** for type checking

### Naming Conventions
- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`
- **Modules**: `lowercase_with_underscores`

### Type Hints
- Always use type hints for function parameters and return values
- Use `from typing import` for complex types
- Use `Optional[T]` for nullable types
- Use `Union[T, U]` for multiple possible types

## TypeScript/JavaScript (Frontend)

### Code Formatting
- Use **Prettier** for code formatting
- Use **ESLint** for linting
- 2-space indentation
- Single quotes for strings
- Trailing commas where valid

### Naming Conventions
- **Variables/Functions**: `camelCase`
- **Components**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Files**: `kebab-case.tsx` or `PascalCase.tsx` for components
- **Interfaces/Types**: `PascalCase` with `I` prefix for interfaces

## Testing

### Test Structure
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)
- One assertion per test when possible
- Use proper test data setup and teardown

## Git Workflow

### Commit Messages
- Use conventional commit format
- Start with type: feat, fix, docs, style, refactor, test, chore
- Keep first line under 50 characters
- Use imperative mood

### Branch Naming
- Use descriptive branch names
- Format: `type/short-description`
- Examples: `feat/video-upload`, `fix/auth-bug`, `docs/api-guide`

---

This style guide is a living document and should be updated as the project evolves. the coding standards and style guidelines for the Cliper project.

## General Principles

1. **Consistency**: Follow existing patterns in the codebase
2. **Readability**: Code should be self-documenting and easy to understand
3. **Maintainability**: Write code that is easy to modify and extend
4. **Performance**: Consider performance implications of code choices
5. **Security**: Always consider security implications

## Python (Backend)

### Code Formatting
- Use **Black** for code formatting (line length: 88 characters)
- Use **isort** for import sorting
- Use **flake8** for linting
- Use **mypy** for type checking

### Naming Conventions
- **Variables/Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`
- **Modules**: `lowercase_with_underscores`

### Type Hints
- Always use type hints for function parameters and return values
- Use `from typing import` for complex types
- Use `Optional[T]` for nullable types
- Use `Union[T, U]` for multiple possible types

### Example:
```python
from typing import Optional, List, Dict, Any
from datetime import datetime

class VideoProcessor:
    """Processes video files for clip generation."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self._config = config
        self.is_initialized = False
    
    async def process_video(
        self, 
        video_path: str, 
        segments: List[Dict[str, float]],
        output_dir: Optional[str] = None
    ) -> List[str]:
        """Process video into clips based on segments.
        
        Args:
            video_path: Path to input video file
            segments: List of segment dictionaries with start/end times
            output_dir: Optional output directory
            
        Returns:
            List of output clip file paths
            
        Raises:
            VideoProcessingError: If processing fails
        """
        if not self.is_initialized:
            raise VideoProcessingError("Processor not initialized")
        
        # Implementation here
        return []
```

### Error Handling
- Use specific exception types
- Always include meaningful error messages
- Log errors appropriately
- Use try/except blocks judiciously

### Async/Await
- Use async/await for I/O operations
- Use `asyncio.gather()` for concurrent operations
- Always handle async context managers properly

## TypeScript/JavaScript (Frontend)

### Code Formatting
- Use **Prettier** for code formatting
- Use **ESLint** for linting
- 2-space indentation
- Single quotes for strings
- Trailing commas where valid

### Naming Conventions
- **Variables/Functions**: `camelCase`
- **Components**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Files**: `kebab-case.tsx` or `PascalCase.tsx` for components
- **Interfaces/Types**: `PascalCase` with `I` prefix for interfaces

### React Components
- Use functional components with hooks
- Use TypeScript interfaces for props
- Use proper prop destructuring
- Use React.memo() for performance optimization when needed

### Example:
```typescript
interface IVideoUploadProps {
  onUploadComplete: (videoId: string) => void;
  maxFileSize?: number;
  acceptedFormats?: string[];
}

const VideoUpload: React.FC<IVideoUploadProps> = ({
  onUploadComplete,
  maxFileSize = 100 * 1024 * 1024, // 100MB
  acceptedFormats = ['mp4', 'mov', 'avi']
}) => {
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);

  const handleFileUpload = useCallback(async (file: File): Promise<void> => {
    if (!validateFile(file)) {
      throw new Error('Invalid file format or size');
    }

    setIsUploading(true);
    try {
      const videoId = await uploadVideo(file, {
        onProgress: setProgress
      });
      onUploadComplete(videoId);
    } catch (error) {
      console.error('Upload failed:', error);
      throw error;
    } finally {
      setIsUploading(false);
      setProgress(0);
    }
  }, [onUploadComplete]);

  return (
    <div className="video-upload">
      {/* Component JSX */}
    </div>
  );
};

export default React.memo(VideoUpload);
```

### State Management
- Use Zustand for global state
- Use React hooks for local state
- Keep state as close to where it's used as possible
- Use proper state normalization for complex data

## CSS/Styling

### Tailwind CSS
- Use Tailwind utility classes
- Create custom components for repeated patterns
- Use responsive design principles
- Follow mobile-first approach

### Class Naming
- Use semantic class names for custom CSS
- Follow BEM methodology when not using Tailwind
- Use CSS modules for component-specific styles

## Database

### SQL Style
- Use uppercase for SQL keywords
- Use snake_case for table and column names
- Always use explicit column names in SELECT statements
- Use meaningful table and column names

### Migrations
- Always create reversible migrations
- Include descriptive comments
- Test migrations on sample data
- Use transactions for complex migrations

## Testing

### Test Structure
- Use descriptive test names
- Follow AAA pattern (Arrange, Act, Assert)
- One assertion per test when possible
- Use proper test data setup and teardown

### Python Tests
```python
import pytest
from unittest.mock import Mock, patch

class TestVideoProcessor:
    """Test suite for VideoProcessor class."""
    
    @pytest.fixture
    def processor(self):
        """Create a VideoProcessor instance for testing."""
        config = {"output_format": "mp4", "quality": "high"}
        return VideoProcessor(config)
    
    async def test_process_video_success(self, processor):
        """Test successful video processing."""
        # Arrange
        video_path = "test_video.mp4"
        segments = [{"start": 0, "end": 30}]
        
        # Act
        result = await processor.process_video(video_path, segments)
        
        # Assert
        assert len(result) == 1
        assert result[0].endswith(".mp4")
```

### TypeScript Tests
```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import VideoUpload from './VideoUpload';

describe('VideoUpload', () => {
  const mockOnUploadComplete = vi.fn();

  beforeEach(() => {
    mockOnUploadComplete.mockClear();
  });

  it('should handle file upload successfully', async () => {
    // Arrange
    render(<VideoUpload onUploadComplete={mockOnUploadComplete} />);
    const file = new File(['video content'], 'test.mp4', { type: 'video/mp4' });
    const input = screen.getByLabelText(/upload video/i);

    // Act
    fireEvent.change(input, { target: { files: [file] } });

    // Assert
    await waitFor(() => {
      expect(mockOnUploadComplete).toHaveBeenCalledWith(expect.any(String));
    });
  });
});
```

## Documentation

### Code Comments
- Use docstrings for all public functions and classes
- Explain **why**, not **what**
- Keep comments up to date with code changes
- Use TODO comments for future improvements

### API Documentation
- Use OpenAPI/Swagger for REST APIs
- Include examples in API documentation
- Document error responses
- Keep documentation in sync with implementation

## Git Workflow

### Commit Messages
- Use conventional commit format
- Start with type: feat, fix, docs, style, refactor, test, chore
- Keep first line under 50 characters
- Use imperative mood

### Example:
```
feat: add video segment analysis endpoint

- Implement AI-powered segment detection
- Add support for multiple video formats
- Include confidence scoring for segments

Closes #123
```

### Branch Naming
- Use descriptive branch names
- Format: `type/short-description`
- Examples: `feat/video-upload`, `fix/auth-bug`, `docs/api-guide`

## Performance Guidelines

### Backend
- Use async/await for I/O operations
- Implement proper caching strategies
- Use database indexes appropriately
- Monitor and log performance metrics

### Frontend
- Use React.memo() for expensive components
- Implement proper code splitting
- Optimize images and assets
- Use proper loading states

## Security Guidelines

### Backend
- Always validate input data
- Use parameterized queries
- Implement proper authentication and authorization
- Never log sensitive information
- Use HTTPS in production

### Frontend
- Sanitize user input
- Use proper CORS configuration
- Implement CSP headers
- Never expose API keys in client code

## Tools and Automation

### Pre-commit Hooks
- Black (Python formatting)
- isort (Python import sorting)
- flake8 (Python linting)
- mypy (Python type checking)
- Prettier (TypeScript/JavaScript formatting)
- ESLint (TypeScript/JavaScript linting)

### CI/CD Pipeline
- Run all tests on every PR
- Check code formatting and linting
- Run security scans
- Build and test Docker images
- Deploy to staging on merge to main

---

This style guide is a living document and should be updated as the project evolves.