import { useState, useCallback } from 'react'
import { toast } from 'sonner'

interface UseAsyncOperationOptions {
  onSuccess?: (data: any) => void
  onError?: (error: Error) => void
  showSuccessToast?: boolean
  showErrorToast?: boolean
  successMessage?: string
  errorMessage?: string
}

interface AsyncOperationState<T> {
  data: T | null
  loading: boolean
  error: Error | null
}

export function useAsyncOperation<T = any>(options: UseAsyncOperationOptions = {}) {
  const [state, setState] = useState<AsyncOperationState<T>>({
    data: null,
    loading: false,
    error: null
  })

  const execute = useCallback(async (asyncFunction: () => Promise<T>) => {
    setState(prev => ({ ...prev, loading: true, error: null }))
    
    try {
      const result = await asyncFunction()
      setState({ data: result, loading: false, error: null })
      
      if (options.onSuccess) {
        options.onSuccess(result)
      }
      
      if (options.showSuccessToast && options.successMessage) {
        toast.success(options.successMessage)
      }
      
      return result
    } catch (error) {
      const errorObj = error instanceof Error ? error : new Error('An unknown error occurred')
      setState(prev => ({ ...prev, loading: false, error: errorObj }))
      
      if (options.onError) {
        options.onError(errorObj)
      }
      
      if (options.showErrorToast !== false) {
        const message = options.errorMessage || errorObj.message || 'An error occurred'
        toast.error(message)
      }
      
      throw errorObj
    }
  }, [options])

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null })
  }, [])

  return {
    ...state,
    execute,
    reset,
    isIdle: !state.loading && !state.error
  }
}