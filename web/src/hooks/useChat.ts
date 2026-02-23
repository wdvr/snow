import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, ApiError } from '../api/client'
import type { ChatMessage, ChatResponse } from '../api/types'
import { useState, useCallback } from 'react'

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

export function useSendMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      message,
      conversationId,
    }: {
      message: string
      conversationId?: string
    }) => api.sendChatMessage(message, conversationId),
    onSuccess: (data: ChatResponse) => {
      // Invalidate conversation list and the specific conversation
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({
        queryKey: ['conversation', data.conversation_id],
      })
    },
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

/** Combined hook for managing a chat session */
export function useChatSession(initialConversationId?: string) {
  const [conversationId, setConversationId] = useState<string | undefined>(
    initialConversationId,
  )
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isRateLimited, setIsRateLimited] = useState(false)

  const conversationQuery = useConversationMessages(conversationId)
  const sendMutation = useSendMessage()

  // Sync messages from server
  const serverMessages = conversationQuery.data
  if (
    serverMessages &&
    serverMessages.length > 0 &&
    messages.length === 0 &&
    conversationId
  ) {
    setMessages(serverMessages)
  }

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

      try {
        const response = await sendMutation.mutateAsync({
          message: content,
          conversationId,
        })

        // Update conversation ID if this was a new conversation
        if (!conversationId) {
          setConversationId(response.conversation_id)
        }

        // Add assistant message
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.response,
          message_id: response.message_id,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, assistantMessage])
      } catch (error) {
        if (error instanceof ApiError && error.status === 429) {
          setIsRateLimited(true)
        }
        // Remove optimistic message on error
        setMessages((prev) => prev.filter((m) => m.message_id !== userMessage.message_id))
        throw error
      }
    },
    [conversationId, sendMutation],
  )

  const startNewConversation = useCallback(() => {
    setConversationId(undefined)
    setMessages([])
    setIsRateLimited(false)
  }, [])

  const loadConversation = useCallback((id: string) => {
    setConversationId(id)
    setMessages([])
  }, [])

  return {
    conversationId,
    messages,
    isLoading: sendMutation.isPending,
    isFetching: conversationQuery.isFetching,
    isRateLimited,
    error: sendMutation.error,
    sendMessage,
    startNewConversation,
    loadConversation,
  }
}
