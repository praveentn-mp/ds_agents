import React, { useState, useRef, useEffect } from 'react';
import { useChatStore } from '../../store/chatStore';
import { useSSE } from '../../hooks/useSSE';
import { chatApi } from '../../api/client';
import { Send, StopCircle, Bot, User, Loader2, Zap, Clock, Cpu, ChevronDown, ChevronRight, MessageSquare, BookOpen, Plus, History, X, Trash2 } from 'lucide-react';
import TracePanel from './TracePanel';
import MarkdownRenderer from './MarkdownRenderer';

export default function ChatInterface() {
  const [input, setInput] = useState('');
  const [showTrace, setShowTrace] = useState(true);
  const [showHistory, setShowHistory] = useState(true);
  const [statsOpen, setStatsOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const {
    conversations,
    messages,
    isStreaming,
    currentConversation,
    tokenStats,
    setConversations,
    setCurrentConversation,
    setMessages,
  } = useChatStore();
  const { sendMessage, cancel } = useSSE();

  // Load conversation list on mount
  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadConversations = async () => {
    try {
      const res = await chatApi.conversations();
      setConversations(res.data);
    } catch {
      // silent — conversations will be loaded when available
    }
  };

  const loadConversation = async (convId: string) => {
    if (convId === currentConversation) return;
    try {
      const res = await chatApi.messages(convId);
      setCurrentConversation(convId);
      setMessages(res.data);
      useChatStore.getState().clearTrace();
      useChatStore.getState().setTokenStats(null);
    } catch {
      // silent
    }
  };

  const startNewChat = () => {
    setCurrentConversation(null);
    setMessages([]);
    useChatStore.getState().clearTrace();
    useChatStore.getState().setTokenStats(null);
  };

  const deleteChat = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await chatApi.deleteConversation(convId);
      if (currentConversation === convId) startNewChat();
      loadConversations();
    } catch {
      // silent
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMsg = {
      id: crypto.randomUUID(),
      conversation_id: currentConversation || '',
      role: 'user',
      content: input,
      metadata: null,
      created_at: new Date().toISOString(),
    };
    useChatStore.getState().addMessage(userMsg);
    sendMessage(input, currentConversation || undefined);
    setInput('');
    // Refresh conversation list after a short delay
    setTimeout(loadConversations, 2000);
  };

  return (
    <div className="flex h-full">
      {/* Conversation history sidebar */}
      {showHistory && (
        <div className="w-64 border-r border-gray-200 bg-gray-50 flex flex-col">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
            <span className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
              <History className="w-4 h-4" /> History
            </span>
            <button
              onClick={() => setShowHistory(false)}
              className="p-1 hover:bg-gray-200 rounded transition"
            >
              <X className="w-3.5 h-3.5 text-gray-400" />
            </button>
          </div>
          <div className="p-3">
            <button
              onClick={startNewChat}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-brand-700 bg-brand-50 hover:bg-brand-100 border border-brand-200 rounded-lg transition"
            >
              <Plus className="w-4 h-4" /> New Chat
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`group flex items-center gap-1 rounded-lg transition ${
                  currentConversation === conv.id
                    ? 'bg-brand-100 text-brand-800'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <button
                  onClick={() => loadConversation(conv.id)}
                  className={`flex-1 text-left px-3 py-2 text-sm truncate ${
                    currentConversation === conv.id ? 'font-medium' : ''
                  }`}
                  title={conv.title || 'Untitled'}
                >
                  {conv.title || 'Untitled chat'}
                </button>
                <button
                  onClick={(e) => deleteChat(conv.id, e)}
                  className="p-1 mr-1 text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 rounded transition"
                  title="Delete conversation"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
            {conversations.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">No conversations yet</p>
            )}
          </div>
        </div>
      )}
      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 bg-white">
          <div className="flex items-center gap-3">
            {!showHistory && (
              <button
                onClick={() => setShowHistory(true)}
                className="p-1.5 hover:bg-gray-100 rounded-lg transition"
                title="Show conversation history"
              >
                <History className="w-4 h-4 text-gray-500" />
              </button>
            )}
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Chat</h2>
              <p className="text-sm text-gray-500">Ask anything about your data</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={startNewChat}
              className="px-3 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 rounded-md hover:bg-brand-100 transition flex items-center gap-1"
            >
              <Plus className="w-3 h-3" /> New Chat
            </button>
            <button
              onClick={() => setShowTrace(!showTrace)}
              className="px-3 py-1.5 text-xs font-medium text-brand-600 bg-brand-50 rounded-md hover:bg-brand-100 transition"
            >
              {showTrace ? 'Hide' : 'Show'} Trace
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mb-4">
                <Bot className="w-8 h-8 text-brand-500" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Welcome to Agent Data Fabric</h3>
              <p className="text-sm text-gray-500 max-w-md">
                Ask questions about your data, manage connectors, or execute workflows.
                Your agent will intelligently route to the right tools.
              </p>
              <div className="mt-6 grid grid-cols-2 gap-3">
                {[
                  'Show me top companies by revenue',
                  'What deals are in the pipeline?',
                  'Which invoices are still pending?',
                  'Summarize revenue by industry',
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => setInput(suggestion)}
                    className="px-4 py-3 text-left text-sm text-gray-600 bg-white border border-gray-200 rounded-lg hover:border-brand-300 hover:text-brand-700 transition"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 animate-fade-in ${msg.role === 'user' ? 'justify-end' : ''}`}>
              {msg.role !== 'user' && (
                <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-brand-600" />
                </div>
              )}
              <div
                className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'max-w-2xl bg-brand-600 text-white'
                    : 'max-w-4xl bg-white border border-gray-200 text-gray-700'
                }`}
              >
                {msg.role === 'user' ? (
                  <span className="whitespace-pre-wrap">{msg.content}</span>
                ) : (
                  <MarkdownRenderer content={msg.content} />
                )}
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-gray-200 flex items-center justify-center flex-shrink-0">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
              )}
            </div>
          ))}

          {isStreaming && (
            <div className="flex gap-3 animate-fade-in">
              <div className="w-8 h-8 rounded-lg bg-brand-100 flex items-center justify-center">
                <Loader2 className="w-4 h-4 text-brand-600 animate-spin" />
              </div>
              <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-brand-400 rounded-full animate-pulse-dot" />
                  <div className="w-2 h-2 bg-brand-400 rounded-full animate-pulse-dot" style={{ animationDelay: '0.2s' }} />
                  <div className="w-2 h-2 bg-brand-400 rounded-full animate-pulse-dot" style={{ animationDelay: '0.4s' }} />
                </div>
              </div>
            </div>
          )}

          {!isStreaming && tokenStats && (
            <div className="animate-fade-in ml-11 max-w-2xl">
              <button
                onClick={() => setStatsOpen(!statsOpen)}
                className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg transition group"
              >
                {statsOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <Zap className="w-3 h-3 text-amber-500" />
                <span className="font-medium">{tokenStats.tokens_input + tokenStats.tokens_output} tokens</span>
                <span className="text-gray-400">·</span>
                <span>{(tokenStats.latency_ms / 1000).toFixed(1)}s</span>
                {tokenStats.model && (
                  <>
                    <span className="text-gray-400">·</span>
                    <span className="text-gray-400">{tokenStats.model}</span>
                  </>
                )}
              </button>

              {statsOpen && (
                <div className="mt-1.5 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-xs space-y-2 animate-fade-in">
                  {/* Model */}
                  {tokenStats.model && (
                    <div className="flex items-center gap-2">
                      <Cpu className="w-3.5 h-3.5 text-gray-400" />
                      <span className="text-gray-500">Model</span>
                      <span className="ml-auto font-medium text-gray-700">{tokenStats.model}</span>
                    </div>
                  )}

                  {/* Tokens */}
                  <div className="flex items-center gap-2">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    <span className="text-gray-500">Tokens</span>
                    <span className="ml-auto font-medium text-gray-700">
                      {tokenStats.tokens_input + tokenStats.tokens_output}
                      <span className="font-normal text-gray-400 ml-1.5">
                        (<span className="text-emerald-600">{tokenStats.tokens_input}↑</span>{' '}
                        <span className="text-blue-600">{tokenStats.tokens_output}↓</span>)
                      </span>
                    </span>
                  </div>

                  {/* Latency */}
                  <div className="flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-gray-400" />
                    <span className="text-gray-500">Latency</span>
                    <span className="ml-auto font-medium text-gray-700">{tokenStats.latency_ms.toLocaleString()}ms</span>
                  </div>

                  {/* LLM Calls */}
                  {tokenStats.llm_calls_count > 0 && (
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-3.5 h-3.5 text-gray-400" />
                      <span className="text-gray-500">LLM Calls</span>
                      <span className="ml-auto font-medium text-gray-700">
                        {tokenStats.llm_calls_count} call{tokenStats.llm_calls_count > 1 ? 's' : ''}
                      </span>
                    </div>
                  )}

                  {/* Prompt Used */}
                  {tokenStats.prompt_used && (
                    <div className="flex items-center gap-2">
                      <BookOpen className="w-3.5 h-3.5 text-gray-400" />
                      <span className="text-gray-500">System Prompt</span>
                      <span className="ml-auto font-mono text-[11px] px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded">
                        {tokenStats.prompt_used}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-gray-200 bg-white">
          <div className="flex gap-3 items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything about your data..."
              className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 transition"
            />
            {isStreaming ? (
              <button type="button" onClick={cancel} className="p-3 text-red-500 hover:bg-red-50 rounded-xl transition">
                <StopCircle className="w-5 h-5" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim()}
                className="p-3 bg-brand-600 text-white rounded-xl hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                <Send className="w-5 h-5" />
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Trace panel */}
      {showTrace && <TracePanel />}
    </div>
  );
}
