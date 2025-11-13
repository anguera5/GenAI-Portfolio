/**
 * Frontend Logger Utility
 * 
 * Provides structured logging for user actions, API calls, and errors.
 * All logs are sent to the browser console and can be extended to send to a remote server.
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR'
}

export interface LogEntry {
  timestamp: string
  level: LogLevel
  category: string
  message: string
  data?: any
  error?: Error
}

class Logger {
  private logs: LogEntry[] = []
  private maxLogs = 1000 // Keep last 1000 logs in memory

  /**
   * Create a log entry with the specified level
   */
  private log(level: LogLevel, category: string, message: string, data?: any, error?: Error): void {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      category,
      message,
      data,
      error
    }

    // Add to in-memory buffer
    this.logs.push(entry)
    if (this.logs.length > this.maxLogs) {
      this.logs.shift() // Remove oldest log
    }

    // Output to console with appropriate styling
    const prefix = `[${entry.timestamp}] [${level}] [${category}]`
    const style = this.getConsoleStyle(level)
    
    switch (level) {
      case LogLevel.DEBUG:
        console.debug(`%c${prefix}`, style, message, data || '')
        break
      case LogLevel.INFO:
        console.info(`%c${prefix}`, style, message, data || '')
        break
      case LogLevel.WARN:
        console.warn(`%c${prefix}`, style, message, data || '')
        break
      case LogLevel.ERROR:
        console.error(`%c${prefix}`, style, message, data || '', error || '')
        if (error && error.stack) {
          console.error('Stack trace:', error.stack)
        }
        break
    }
  }

  private getConsoleStyle(level: LogLevel): string {
    const styles: Record<LogLevel, string> = {
      [LogLevel.DEBUG]: 'color: #888; font-weight: normal',
      [LogLevel.INFO]: 'color: #2196F3; font-weight: bold',
      [LogLevel.WARN]: 'color: #FF9800; font-weight: bold',
      [LogLevel.ERROR]: 'color: #F44336; font-weight: bold'
    }
    return styles[level]
  }

  /**
   * Log debug information (development only)
   */
  debug(category: string, message: string, data?: any): void {
    if (import.meta.env.DEV) {
      this.log(LogLevel.DEBUG, category, message, data)
    }
  }

  /**
   * Log informational messages
   */
  info(category: string, message: string, data?: any): void {
    this.log(LogLevel.INFO, category, message, data)
  }

  /**
   * Log warnings
   */
  warn(category: string, message: string, data?: any): void {
    this.log(LogLevel.WARN, category, message, data)
  }

  /**
   * Log errors
   */
  error(category: string, message: string, error?: Error | any, data?: any): void {
    const errorObj = error instanceof Error ? error : new Error(String(error))
    this.log(LogLevel.ERROR, category, message, data, errorObj)
  }

  /**
   * Log user actions (button clicks, form submissions, etc.)
   */
  userAction(action: string, details?: any): void {
    this.info('USER_ACTION', action, details)
  }

  /**
   * Log API requests
   */
  apiRequest(method: string, url: string, data?: any): void {
    this.info('API_REQUEST', `${method} ${url}`, data)
  }

  /**
   * Log API responses
   */
  apiResponse(method: string, url: string, status: number, duration: number, data?: any): void {
    this.info('API_RESPONSE', `${method} ${url} - ${status} (${duration}ms)`, data)
  }

  /**
   * Log API errors
   */
  apiError(method: string, url: string, error: any, duration?: number): void {
    const message = duration 
      ? `${method} ${url} - Failed (${duration}ms)` 
      : `${method} ${url} - Failed`
    this.error('API_ERROR', message, error)
  }

  /**
   * Log navigation events
   */
  navigation(from: string, to: string): void {
    this.info('NAVIGATION', `${from} → ${to}`)
  }

  /**
   * Get all logs (for debugging or export)
   */
  getLogs(): LogEntry[] {
    return [...this.logs]
  }

  /**
   * Clear all logs
   */
  clearLogs(): void {
    this.logs = []
    console.clear()
  }

  /**
   * Export logs as JSON (useful for debugging)
   */
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2)
  }
}

// Export singleton instance
export const logger = new Logger()

// Export default for convenience
export default logger
