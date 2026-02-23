import { useEffect, useRef } from 'react'
import { Snowflake, MessageCircle, Loader2, Wrench } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../../api/types'
import { ChatMessage, TypingIndicator } from './ChatMessage'

interface ChatWindowProps {
  messages: ChatMessageType[]
  isLoading: boolean
  statusMessage?: string | null
  activeTools?: string[]
  onSuggestionClick?: (text: string) => void
}

export function ChatWindow({
  messages,
  isLoading,
  statusMessage,
  activeTools,
  onSuggestionClick,
}: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading, statusMessage])

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center mx-auto mb-4">
            <Snowflake className="w-8 h-8 text-blue-500" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">
            Ask me about ski conditions
          </h2>
          <p className="text-gray-500 text-sm mb-6">
            I can help you find the best powder, compare resorts, or check
            conditions at any resort worldwide.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {[
              'Where is the best powder right now?',
              'Compare Whistler and Revelstoke conditions',
              'Will it snow at Park City this week?',
              'Best resorts in the Alps for beginners',
            ].map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => onSuggestionClick?.(suggestion)}
                className="text-left px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 hover:border-gray-300 transition-colors"
              >
                <MessageCircle className="w-3.5 h-3.5 inline-block mr-1.5 opacity-50" />
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scroll">
      {messages.map((message) => (
        <ChatMessage key={message.message_id} message={message} />
      ))}
      {isLoading && !statusMessage && activeTools?.length === 0 && <TypingIndicator />}
      {isLoading && (statusMessage || (activeTools && activeTools.length > 0)) && (
        <div className="flex justify-start">
          <div className="bg-white rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm border border-gray-100 max-w-sm">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
              <span>{statusMessage || 'Thinking...'}</span>
            </div>
            {activeTools && activeTools.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {activeTools.map((tool) => (
                  <span
                    key={tool}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-50 text-blue-600 text-xs font-medium"
                  >
                    <Wrench className="w-3 h-3" />
                    {tool.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
