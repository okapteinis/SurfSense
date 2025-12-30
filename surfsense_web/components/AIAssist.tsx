'use client'

import { useState, useRef } from 'react'
import { Sparkles, X } from 'lucide-react'

interface AIAssistButtonProps {
  onInsert: (text: string) => void
  context?: string
  userInput?: string
  className?: string
}

export function AIAssistButton({ onInsert, context, userInput, className = '' }: AIAssistButtonProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [currentCommand, setCurrentCommand] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  // Task 14: AbortController for request cancellation
  const abortControllerRef = useRef<AbortController | null>(null)

  const commands = [
    { id: 'draft', label: 'Draft Response', requiresContext: true },
    { id: 'improve', label: 'Improve Text', requiresInput: true },
    { id: 'shorten', label: 'Make Shorter', requiresInput: true },
    { id: 'translate', label: 'Translate to English', requiresInput: true },
    { id: 'formal', label: 'Make Formal', requiresInput: true },
    { id: 'casual', label: 'Make Casual', requiresInput: true },
  ]

  // Task 14: Cancel ongoing request
  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsLoading(false)
    setCurrentCommand(null)
    setProgress(0)
    setError(null)
  }

  const runAssist = async (command: string) => {
    setIsLoading(true)
    setCurrentCommand(command)
    setError(null)
    setProgress(0)

    // Task 14: Create new AbortController for this request
    abortControllerRef.current = new AbortController()

    try {
      // Task 13: Better error handling with user feedback
      const response = await fetch('/api/v1/assist/', {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_input: userInput || '',
          context: context || '',
          command: command
        }),
        // Task 14: Support request cancellation
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        // Task 13: Display specific error messages
        if (response.status === 429) {
          throw new Error('Rate limit exceeded. Please wait a moment before trying again.')
        } else if (response.status === 400) {
          const errorData = await response.json().catch(() => ({}))
          throw new Error(errorData.detail || 'Invalid request. Please check your input.')
        } else if (response.status === 500) {
          throw new Error('AI service temporarily unavailable. Please try again later.')
        } else {
          throw new Error(`Request failed with status ${response.status}`)
        }
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body received')
      }

      let result = ''
      const decoder = new TextDecoder()
      let bytesReceived = 0

      // Task 16: Track progress while streaming
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        bytesReceived += value.length
        result += decoder.decode(value, { stream: true })

        // Task 16: Update progress indicator (approximate)
        setProgress(Math.min(95, Math.floor(bytesReceived / 100)))
      }

      // Task 16: Complete progress
      setProgress(100)

      // Task 13: Insert result and close
      onInsert(result.trim())
      setIsOpen(false)
      setError(null)

    } catch (error: any) {
      // Task 14: Handle abort separately
      if (error.name === 'AbortError') {
        console.log('Request cancelled by user')
        return
      }

      // Task 13: Display error to user instead of just console.error
      console.error('AI assist error:', error)
      const errorMessage = error.message || 'Failed to generate AI response. Please try again.'
      setError(errorMessage)
    } finally {
      setIsLoading(false)
      setCurrentCommand(null)
      abortControllerRef.current = null
      // Reset progress after a brief delay
      setTimeout(() => setProgress(0), 500)
    }
  }

  const availableCommands = commands.filter(cmd => {
    if (cmd.requiresContext && !context) return false
    if (cmd.requiresInput && !userInput) return false
    return true
  })

  if (availableCommands.length === 0) {
    return null
  }

  // Task 15: Keyboard navigation handler
  const handleKeyDown = (event: React.KeyboardEvent, callback: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      callback()
    }
  }

  return (
    <div className={`relative ${className}`}>
      {/* Task 15: ARIA attributes for accessibility */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        aria-label="Open AI assistant menu"
        aria-expanded={isOpen}
        aria-haspopup="menu"
      >
        <Sparkles size={16} aria-hidden="true" />
        AI Assist
      </button>

      {/* Command menu */}
      {isOpen && !isLoading && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div
            className="absolute z-50 mt-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg border border-gray-200 dark:border-gray-700 py-1"
            role="menu"
            aria-label="AI assistant commands"
          >
            {availableCommands.map((cmd, index) => (
              <button
                key={cmd.id}
                onClick={() => runAssist(cmd.id)}
                onKeyDown={(e) => handleKeyDown(e, () => runAssist(cmd.id))}
                disabled={isLoading}
                className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                role="menuitem"
                tabIndex={0}
                aria-label={cmd.label}
              >
                {cmd.label}
              </button>
            ))}
          </div>
        </>
      )}

      {/* Task 16: Comprehensive loading state with progress */}
      {isLoading && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center bg-white/90 dark:bg-gray-900/90 rounded-md z-50"
          role="status"
          aria-live="polite"
          aria-label={`AI is ${currentCommand || 'processing'}. Progress: ${progress}%`}
        >
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600" aria-hidden="true"></div>
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {currentCommand ? `${currentCommand.charAt(0).toUpperCase() + currentCommand.slice(1)}ing...` : 'Processing...'}
            </span>
          </div>

          {/* Task 16: Progress bar */}
          {progress > 0 && (
            <div className="w-32 h-1 bg-gray-200 dark:bg-gray-700 rounded-full mt-2 overflow-hidden">
              <div
                className="h-full bg-purple-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
                aria-hidden="true"
              />
            </div>
          )}

          {/* Task 14: Cancel button */}
          <button
            onClick={cancelRequest}
            className="mt-3 px-3 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 transition-colors flex items-center gap-1"
            aria-label="Cancel AI request"
          >
            <X size={12} aria-hidden="true" />
            Cancel
          </button>
        </div>
      )}

      {/* Task 13: Error display */}
      {error && !isLoading && (
        <div
          className="absolute z-50 mt-2 w-64 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 shadow-lg"
          role="alert"
          aria-live="assertive"
        >
          <div className="flex items-start gap-2">
            <div className="flex-1">
              <p className="text-sm text-red-800 dark:text-red-200 font-medium">Error</p>
              <p className="text-sm text-red-700 dark:text-red-300 mt-1">{error}</p>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200"
              aria-label="Dismiss error"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
