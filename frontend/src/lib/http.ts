import axios, { AxiosError } from 'axios'
import { useNotifyStore } from '../stores/notify'
import { logger } from './logger'

// Create a singleton axios instance
// Let Vite proxy /api to backend; baseURL left empty so relative URLs work
// Default to a generous timeout (e.g., 5 minutes) so large DB queries aren't cut off locally.
// Override via VITE_HTTP_TIMEOUT (ms). Use 0 to disable.
const parsed = Number((import.meta as any).env?.VITE_HTTP_TIMEOUT)
const timeout = Number.isFinite(parsed) ? parsed : 300_000
export const http = axios.create({ timeout })

// Helper to safely access store outside of setup by importing on demand
function notifyError(message: string) {
  try {
    const store = useNotifyStore()
    store.error(message)
  } catch {
    // Pinia not ready yet; fall back
    // eslint-disable-next-line no-alert
    if (typeof window !== 'undefined') window.alert(message)
    // else ignore
  }
}

// Request interceptor to log outgoing requests
http.interceptors.request.use(
  (config) => {
    const startTime = Date.now()
    // Store start time for duration calculation
    config.metadata = { startTime }
    
    // Log the request (exclude sensitive data like API keys)
    const sanitizedData = config.data ? { ...config.data } : undefined
    if (sanitizedData && sanitizedData.api_key) {
      sanitizedData.api_key = '[REDACTED]'
    }
    
    logger.apiRequest(
      config.method?.toUpperCase() || 'GET',
      config.url || '',
      sanitizedData
    )
    
    return config
  },
  (err: AxiosError) => {
    logger.error('HTTP', 'Request setup failed', err)
    return Promise.reject(err)
  }
)

// Response interceptor to log responses and errors
http.interceptors.response.use(
  (res) => {
    // Calculate request duration
    const duration = res.config.metadata?.startTime 
      ? Date.now() - res.config.metadata.startTime 
      : 0
    
    // Log successful response (don't log full response body to avoid clutter)
    logger.apiResponse(
      res.config.method?.toUpperCase() || 'GET',
      res.config.url || '',
      res.status,
      duration,
      { status: res.status, statusText: res.statusText }
    )
    
    return res
  },
  (err: AxiosError<any>) => {
    // Calculate request duration
    const duration = err.config?.metadata?.startTime 
      ? Date.now() - err.config.metadata.startTime 
      : undefined
    
    // Prefer FastAPI-style detail if provided
    const status = err.response?.status
    const detail = (err.response?.data as any)?.detail
    const message = detail
      || (err.message || 'Network error')
    const prefix = status ? `[${status}] ` : ''
    
    // Log the error with full context
    logger.apiError(
      err.config?.method?.toUpperCase() || 'UNKNOWN',
      err.config?.url || 'unknown',
      {
        status,
        message: detail || err.message,
        responseData: err.response?.data,
        code: err.code
      },
      duration
    )
    
    notifyError(prefix + String(message))
    return Promise.reject(err)
  }
)

// Add metadata type to axios config
declare module 'axios' {
  export interface AxiosRequestConfig {
    metadata?: {
      startTime: number
    }
  }
}

export default http
