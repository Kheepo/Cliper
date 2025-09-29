// Error types for the application

export class AppError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500
  ) {
    super(message)
    this.name = 'AppError'
  }
}

export class AuthError extends AppError {
  constructor(message: string = 'Authentication failed') {
    super(message, 'AUTH_ERROR', 401)
    this.name = 'AuthError'
  }
}

export class ValidationError extends AppError {
  constructor(message: string = 'Validation failed') {
    super(message, 'VALIDATION_ERROR', 400)
    this.name = 'ValidationError'
  }
}

export class NetworkError extends AppError {
  constructor(message: string = 'Network error occurred') {
    super(message, 'NETWORK_ERROR', 500)
    this.name = 'NetworkError'
  }
}

export class UploadError extends AppError {
  constructor(message: string = 'Upload failed') {
    super(message, 'UPLOAD_ERROR', 500)
    this.name = 'UploadError'
  }
}

export class ServerError extends AppError {
  constructor(message: string = 'Server error occurred') {
    super(message, 'SERVER_ERROR', 500)
    this.name = 'ServerError'
  }
}

export class APIError extends AppError {
  constructor(message: string = 'API error occurred', statusCode: number = 500) {
    super(message, 'API_ERROR', statusCode)
    this.name = 'APIError'
  }
}

// Error type guards
export const isAuthError = (error: any): error is AuthError => {
  return error instanceof AuthError || error?.name === 'AuthError'
}

export const isValidationError = (error: any): error is ValidationError => {
  return error instanceof ValidationError || error?.name === 'ValidationError'
}

export const isNetworkError = (error: any): error is NetworkError => {
  return error instanceof NetworkError || error?.name === 'NetworkError'
}

export const isUploadError = (error: any): error is UploadError => {
  return error instanceof UploadError || error?.name === 'UploadError'
}

export const isServerError = (error: any): error is ServerError => {
  return error instanceof ServerError || error?.name === 'ServerError'
}

// Error factory functions
export const createAuthError = (message?: string) => new AuthError(message)
export const createValidationError = (message?: string) => new ValidationError(message)
export const createNetworkError = (message?: string) => new NetworkError(message)
export const createUploadError = (message?: string) => new UploadError(message)
export const createServerError = (message?: string) => new ServerError(message)

// Error handling utilities
export const getErrorMessage = (error: unknown): string => {
  if (error instanceof Error) {
    return error.message
  }
  if (typeof error === 'string') {
    return error
  }
  return 'An unknown error occurred'
}

export const getErrorCode = (error: unknown): string => {
  if (error instanceof AppError) {
    return error.code
  }
  return 'UNKNOWN_ERROR'
}

export const getErrorStatusCode = (error: unknown): number => {
  if (error instanceof AppError) {
    return error.statusCode
  }
  return 500
}