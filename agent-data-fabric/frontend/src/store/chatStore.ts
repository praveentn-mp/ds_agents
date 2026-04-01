import { create } from 'zustand';
import type { Conversation, Message, TraceEvent } from '../types';

export interface TokenStats {
  tokens_input: number;
  tokens_output: number;
  tokens_cache: number;
  latency_ms: number;
  llm_calls_count: number;
  model?: string;
  prompt_used?: string;
}

interface ChatState {
  conversations: Conversation[];
  currentConversation: string | null;
  messages: Message[];
  traceEvents: TraceEvent[];
  isStreaming: boolean;
  tokenStats: TokenStats | null;
  setConversations: (convs: Conversation[]) => void;
  setCurrentConversation: (id: string | null) => void;
  setMessages: (msgs: Message[]) => void;
  addMessage: (msg: Message) => void;
  addTraceEvent: (event: TraceEvent) => void;
  clearTrace: () => void;
  setStreaming: (val: boolean) => void;
  setTokenStats: (stats: TokenStats | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  conversations: [],
  currentConversation: null,
  messages: [],
  traceEvents: [],
  isStreaming: false,
  tokenStats: null,

  setConversations: (convs) => set({ conversations: convs }),
  setCurrentConversation: (id) => set({ currentConversation: id }),
  setMessages: (msgs) => set({ messages: msgs }),
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  addTraceEvent: (event) => set((s) => ({ traceEvents: [...s.traceEvents, event] })),
  clearTrace: () => set({ traceEvents: [] }),
  setStreaming: (val) => set({ isStreaming: val }),
  setTokenStats: (stats) => set({ tokenStats: stats }),
}));
