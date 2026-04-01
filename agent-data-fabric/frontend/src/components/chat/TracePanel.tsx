import React from 'react';
import { useChatStore } from '../../store/chatStore';
import { Activity, CheckCircle2, AlertCircle, Clock, Loader2 } from 'lucide-react';

const statusIcon = {
  running: <Loader2 className="w-3.5 h-3.5 text-blue-500 animate-spin" />,
  success: <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />,
  error: <AlertCircle className="w-3.5 h-3.5 text-red-500" />,
};

const typeColors: Record<string, string> = {
  intent_classification: 'bg-purple-50 text-purple-700 border-purple-200',
  capability_resolution: 'bg-blue-50 text-blue-700 border-blue-200',
  query: 'bg-green-50 text-green-700 border-green-200',
  tool_call: 'bg-orange-50 text-orange-700 border-orange-200',
  rag: 'bg-teal-50 text-teal-700 border-teal-200',
  response: 'bg-gray-50 text-gray-700 border-gray-200',
  error: 'bg-red-50 text-red-700 border-red-200',
};

export default function TracePanel() {
  const { traceEvents } = useChatStore();

  return (
    <div className="w-80 border-l border-gray-200 bg-white overflow-y-auto">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100">
        <Activity className="w-4 h-4 text-brand-500" />
        <h3 className="text-sm font-semibold text-gray-900">Execution Trace</h3>
        <span className="ml-auto text-xs text-gray-400">{traceEvents.length} steps</span>
      </div>

      <div className="p-3 space-y-2">
        {traceEvents.length === 0 && (
          <p className="text-xs text-gray-400 text-center py-8">
            Trace events will appear here during chat
          </p>
        )}

        {traceEvents.map((event, i) => (
          <div
            key={i}
            className={`rounded-lg border p-3 text-xs animate-fade-in ${
              typeColors[event.type] || typeColors.response
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              {statusIcon[event.status as keyof typeof statusIcon] || statusIcon.running}
              <span className="font-medium capitalize">{event.type.replace(/_/g, ' ')}</span>
              {event.duration_ms && (
                <span className="ml-auto flex items-center gap-1 opacity-70">
                  <Clock className="w-3 h-3" />
                  {event.duration_ms}ms
                </span>
              )}
            </div>
            {event.agent && (
              <p className="text-[11px] opacity-70">Agent: {event.agent}</p>
            )}
            {event.tool && (
              <p className="text-[11px] opacity-70">Tool: {event.tool}</p>
            )}
            {event.payload && (
              <details className="mt-1">
                <summary className="cursor-pointer text-[11px] opacity-60 hover:opacity-100">
                  Payload
                </summary>
                <pre className="mt-1 text-[10px] bg-black/5 rounded p-1.5 overflow-x-auto">
                  {JSON.stringify(event.payload, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
