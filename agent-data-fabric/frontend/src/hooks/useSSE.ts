import { useCallback, useRef } from 'react';
import { useChatStore } from '../store/chatStore';

export function useSSE() {
  const abortRef = useRef<AbortController | null>(null);
  const { addMessage, addTraceEvent, setStreaming, clearTrace, setTokenStats } = useChatStore();

  const sendMessage = useCallback(
    async (message: string, conversationId?: string) => {
      if (abortRef.current) abortRef.current.abort();
      abortRef.current = new AbortController();

      clearTrace();
      setStreaming(true);
      setTokenStats(null);

      const token = localStorage.getItem('adf_token');
      let responseText = '';

      try {
        const response = await fetch('/api/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ message, conversation_id: conversationId }),
          signal: abortRef.current.signal,
        });

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) return;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value, { stream: true });
          const lines = text.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.event === 'trace_step') {
                  addTraceEvent(data.data);
                } else if (data.event === 'token') {
                  responseText += data.data.content;
                } else if (data.event === 'done') {
                  if (responseText) {
                    addMessage({
                      id: crypto.randomUUID(),
                      conversation_id: data.data.conversation_id || '',
                      role: 'assistant',
                      content: responseText,
                      metadata: null,
                      created_at: new Date().toISOString(),
                    });
                  }
                  // Capture token stats
                  const d = data.data;
                  if (d.tokens || d.latency_ms) {
                    setTokenStats({
                      tokens_input: d.tokens?.input ?? 0,
                      tokens_output: d.tokens?.output ?? 0,
                      tokens_cache: d.tokens?.cache ?? 0,
                      latency_ms: d.latency_ms ?? 0,
                      llm_calls_count: d.llm_calls_count ?? 0,
                      model: d.model,
                      prompt_used: d.prompt_used,
                    });
                  }
                }
              } catch {
                // skip malformed lines
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          console.error('SSE error:', err);
        }
      } finally {
        setStreaming(false);
      }
    },
    [addMessage, addTraceEvent, clearTrace, setStreaming, setTokenStats]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, [setStreaming]);

  return { sendMessage, cancel };
}
