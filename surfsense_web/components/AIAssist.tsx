'use client'

import { useState } from 'react'
import { Sparkles } from 'lucide-react'

interface AIAssistButtonProps {
  onInsert: (text: string) => void
  context?: string
  userInput?: string
  className?: string
}

export function AIAssistButton({ onInsert, context, userInput, className = '' }: AIAssistButtonProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const commands = [
    { id: 'draft', label: 'Draft Response', requiresContext: true },
    { id: 'improve', label: 'Improve Text', requiresInput: true },
    { id: 'shorten', label: 'Make Shorter', requiresInput: true },
    { id: 'translate', label: 'Translate to English', requiresInput: true },
    { id: 'formal', label: 'Make Formal', requiresInput: true },
    { id: 'casual', label: 'Make Casual', requiresInput: true },
  ]

  const runAssist = async (command: string) => {
    setIsLoading(true)

    try {
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
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      let result = ''
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        result += decoder.decode(value, { stream: true })
      }

      onInsert(result.trim())
      setIsOpen(false)

    } catch (error) {
      console.error('AI assist error:', error)
      alert('Failed to generate AI response. Please try again.')
    } finally {
      setIsLoading(false)
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

  return (
    <div className={`relative ${className}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={isLoading}
        className="flex items-center gap-2 px-3 py-1.5 text-sm bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        <Sparkles size={16} />
        AI Assist
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute z-50 mt-2 w-56 bg-white dark:bg-gray-800 shadow-lg rounded-lg border border-gray-200 dark:border-gray-700 py-1">
            {availableCommands.map(cmd => (
              <button
                key={cmd.id}
                onClick={() => runAssist(cmd.id)}
                disabled={isLoading}
                className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {cmd.label}
              </button>
            ))}
          </div>
        </>
      )}

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-900/50 rounded-md">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-purple-600"></div>
        </div>
      )}
    </div>
  )
}
