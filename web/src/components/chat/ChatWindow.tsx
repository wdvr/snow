import { useEffect, useRef } from 'react'
import { Snowflake, MessageCircle } from 'lucide-react'
import type { ChatMessage as ChatMessageType } from '../../api/types'
import { ChatMessage, TypingIndicator } from './ChatMessage'

interface ChatWindowProps {
  messages: ChatMessageType[]
  isLoading: boolean
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

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
      {isLoading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
