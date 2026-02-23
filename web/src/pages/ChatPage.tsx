import { useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Plus,
  MessageSquare,
  Trash2,
  ChevronLeft,
  AlertTriangle,
} from 'lucide-react'
import { useState } from 'react'
import { useAuth } from '../auth/useAuth'
import { useChatSession, useConversations, useDeleteConversation } from '../hooks/useChat'
import { ChatWindow } from '../components/chat/ChatWindow'
import { ChatInput } from '../components/chat/ChatInput'
import { formatTimestamp } from '../utils/format'

export function ChatPage() {
  const { conversationId: urlConversationId } = useParams<{
    conversationId: string
  }>()
  const navigate = useNavigate()
  const { isAuthenticated, loginAsGuest } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)

  const {
    conversationId,
    messages,
    isLoading,
    isRateLimited,
    sendMessage,
    startNewConversation,
    loadConversation,
  } = useChatSession(urlConversationId)

  const { data: conversations } = useConversations()
  const deleteConversation = useDeleteConversation()

  // Auto-authenticate as guest for chat if not already authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      loginAsGuest().catch(() => {
        // Silent - guest auth may fail, chat still works without auth
      })
    }
  }, [isAuthenticated, loginAsGuest])

  // Sync URL with conversation ID
  useEffect(() => {
    if (conversationId && conversationId !== urlConversationId) {
      navigate(`/chat/${conversationId}`, { replace: true })
    }
  }, [conversationId, urlConversationId, navigate])

  // Load conversation from URL
  useEffect(() => {
    if (urlConversationId && urlConversationId !== conversationId) {
      loadConversation(urlConversationId)
    }
  }, [urlConversationId, conversationId, loadConversation])

  const handleSend = useCallback(
    async (content: string) => {
      setSendError(null)
      try {
        await sendMessage(content)
      } catch (err) {
        if (err instanceof Error) {
          setSendError(err.message)
        }
      }
    },
    [sendMessage],
  )

  const handleNewConversation = useCallback(() => {
    startNewConversation()
    navigate('/chat')
    setSidebarOpen(false)
  }, [startNewConversation, navigate])

  const handleSelectConversation = useCallback(
    (id: string) => {
      loadConversation(id)
      navigate(`/chat/${id}`)
      setSidebarOpen(false)
    },
    [loadConversation, navigate],
  )

  const handleDeleteConversation = useCallback(
    async (id: string, e: React.MouseEvent) => {
      e.stopPropagation()
      try {
        await deleteConversation.mutateAsync(id)
        if (conversationId === id) {
          handleNewConversation()
        }
      } catch {
        // Silently handle delete error
      }
    },
    [deleteConversation, conversationId, handleNewConversation],
  )

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Sidebar overlay for mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-30 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-72 bg-white border-r border-gray-200 flex flex-col transition-transform lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="p-3 border-b border-gray-100">
          <button
            onClick={handleNewConversation}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {conversations?.map((conv) => (
            <button
              key={conv.conversation_id}
              onClick={() => handleSelectConversation(conv.conversation_id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors group flex items-center gap-2 ${
                conversationId === conv.conversation_id
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
            >
              <MessageSquare className="w-4 h-4 shrink-0 opacity-50" />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">{conv.title}</p>
                <p className="text-xs text-gray-400 truncate">
                  {formatTimestamp(conv.last_message_at)}
                </p>
              </div>
              <button
                onClick={(e) => handleDeleteConversation(conv.conversation_id, e)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-200 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5 text-gray-400" />
              </button>
            </button>
          ))}
          {conversations?.length === 0 && (
            <p className="text-center text-sm text-gray-400 py-8">
              No conversations yet
            </p>
          )}
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile sidebar toggle */}
        <div className="lg:hidden flex items-center gap-2 p-3 border-b border-gray-100 bg-white">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg text-gray-600 hover:bg-gray-100"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm font-medium text-gray-700 truncate">
            {conversations?.find((c) => c.conversation_id === conversationId)?.title ??
              'New Conversation'}
          </span>
        </div>

        {/* Messages */}
        <ChatWindow messages={messages} isLoading={isLoading} />

        {/* Rate limit + error banners */}
        {isRateLimited && (
          <div className="mx-4 mb-2 flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>
              Rate limit reached. Please try again later.
              {!isAuthenticated && ' Sign in for more messages.'}
            </span>
          </div>
        )}
        {sendError && !isRateLimited && (
          <div className="mx-4 mb-2 flex items-center gap-2 px-4 py-2 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{sendError}</span>
          </div>
        )}

        {/* Input */}
        <div className="p-4 bg-gray-50 border-t border-gray-100">
          <div className="max-w-3xl mx-auto">
            <ChatInput
              onSend={handleSend}
              disabled={isLoading}
              placeholder={
                isRateLimited
                  ? 'Rate limit reached. Please try again later.'
                  : 'Ask about ski conditions at any resort...'
              }
            />
            <p className="text-xs text-gray-400 text-center mt-2">
              Powered by AI. Responses may not always be accurate.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
