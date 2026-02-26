import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { ChatMessage } from '../api/types'
import { useState, useCallback, useRef, useEffect } from 'react'

const STREAM_URL = import.meta.env.VITE_CHAT_STREAM_URL || ''

export function useConversations() {
  return useQuery({
    queryKey: ['conversations'],
    queryFn: () => api.getConversations(),
    staleTime: 30 * 1000,
  })
}

export function useConversationMessages(conversationId: string | undefined) {
  return useQuery({
    queryKey: ['conversation', conversationId],
    queryFn: () => api.getConversation(conversationId!),
    staleTime: 0,
    enabled: !!conversationId,
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (conversationId: string) => api.deleteConversation(conversationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
  })
}

interface StreamEvent {
  type: 'status' | 'tool_start' | 'tool_done' | 'text_delta' | 'done' | 'error'
  message?: string
  tool?: string
  input?: Record<string, unknown>
  duration_ms?: number
  text?: string
  conversation_id?: string
  message_id?: string
}

/** Combined hook for managing a chat session with streaming */
export function useChatSession(initialConversationId?: string) {
  const [conversationId, setConversationId] = useState<string | undefined>(
    initialConversationId,
  )
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isRateLimited, setIsRateLimited] = useState(false)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [activeTools, setActiveTools] = useState<string[]>([])
  const [error, setError] = useState<Error | null>(null)
  const queryClient = useQueryClient()
  const abortRef = useRef<AbortController | null>(null)

  const conversationQuery = useConversationMessages(conversationId)

  // Sync messages from server
  const serverMessages = conversationQuery.data
  useEffect(() => {
    if (
      serverMessages &&
      serverMessages.length > 0 &&
      messages.length === 0 &&
      conversationId
    ) {
      setMessages(serverMessages)
    }
  }, [serverMessages, conversationId])

  const sendMessage = useCallback(
    async (content: string) => {
      // Add optimistic user message
      const userMessage: ChatMessage = {
        role: 'user',
        content,
        message_id: `temp-${Date.now()}`,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])
      setIsRateLimited(false)
      setError(null)
      setIsLoading(true)
      setStatusMessage(null)
      setActiveTools([])

      // Try streaming if URL is configured
      if (STREAM_URL) {
        try {
          await sendMessageStream(content, userMessage)
          return
        } catch (err) {
          // Fall back to non-streaming on stream failure
          console.warn('Stream failed, falling back to REST:', err)
        }
      }

      // Fallback: non-streaming REST call
      try {
        const response = await api.sendChatMessage(content, conversationId)
        if (!conversationId) {
          setConversationId(response.conversation_id)
        }
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.response,
          message_id: response.message_id,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMessage])
        queryClient.invalidateQueries({ queryKey: ['conversations'] })
      } catch (err) {
        if (err instanceof ApiError && err.status === 429) {
          setIsRateLimited(true)
        }
        setMessages((prev) => prev.filter((m) => m.message_id !== userMessage.message_id))
        setError(err instanceof Error ? err : new Error('Failed to send message'))
        throw err
      } finally {
        setIsLoading(false)
        setStatusMessage(null)
        setActiveTools([])
      }
    },
    [conversationId, queryClient],
  )

  const sendMessageStream = useCallback(
    async (content: string, _userMessage: ChatMessage) => {
      const controller = new AbortController()
      abortRef.current = controller

      const token = localStorage.getItem('snow_access_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const response = await fetch(STREAM_URL, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          message: content,
          conversation_id: conversationId,
        }),
        signal: controller.signal,
      })

      if (!response.ok || !response.body) {
        throw new Error(`Stream request failed: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let assistantText = ''
      let assistantId = ''
      let newConversationId = ''

      // Add a placeholder assistant message immediately
      const placeholderId = `stream-${Date.now()}`
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '',
          message_id: placeholderId,
          created_at: new Date().toISOString(),
        },
      ])

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event: StreamEvent = JSON.parse(line.slice(6))
              switch (event.type) {
                case 'status':
                  setStatusMessage(event.message || null)
                  break
                case 'tool_start':
                  setStatusMessage(event.message || `Running ${event.tool}...`)
                  setActiveTools((prev) => [...prev, event.tool || ''])
                  break
                case 'tool_done':
                  setActiveTools((prev) => prev.filter((t) => t !== event.tool))
                  break
                case 'text_delta':
                  assistantText += event.text || ''
                  setStatusMessage(null)
                  setMessages((prev) =>
                    prev.map((m) =>
                      m.message_id === placeholderId
                        ? { ...m, content: assistantText }
                        : m,
                    ),
                  )
                  break
                case 'done':
                  assistantId = event.message_id || ''
                  newConversationId = event.conversation_id || ''
                  break
                case 'error':
                  throw new Error(event.message || 'Chat error')
              }
            } catch (parseErr) {
              if (parseErr instanceof Error && parseErr.message === 'Chat error') throw parseErr
            }
          }
        }
      } finally {
        setIsLoading(false)
        setStatusMessage(null)
        setActiveTools([])
        abortRef.current = null
      }

      // Update the placeholder with final ID
      if (assistantId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.message_id === placeholderId
              ? { ...m, message_id: assistantId, content: assistantText }
              : m,
          ),
        )
      }

      if (newConversationId && !conversationId) {
        setConversationId(newConversationId)
      }

      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    },
    [conversationId, queryClient],
  )

  const startNewConversation = useCallback(() => {
    setConversationId(undefined)
    setMessages([])
    setIsRateLimited(false)
    setError(null)
    setStatusMessage(null)
    setActiveTools([])
  }, [])

  const loadConversation = useCallback((id: string) => {
    setConversationId(id)
    setMessages([])
  }, [])

  return {
    conversationId,
    messages,
    isLoading,
    isFetching: conversationQuery.isFetching,
    isRateLimited,
    statusMessage,
    activeTools,
    error,
    sendMessage,
    startNewConversation,
    loadConversation,
  }
}
