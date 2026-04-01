import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronLeft, ChevronRight, Copy, Check } from 'lucide-react';

const PAGE_SIZE = 10;

function PaginatedTable({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);

  // Extract thead and tbody from children
  let headRows: React.ReactNode = null;
  let bodyRows: React.ReactElement[] = [];

  React.Children.forEach(children, (child: any) => {
    if (child?.type === 'thead') headRows = child;
    if (child?.type === 'tbody') {
      React.Children.forEach(child.props.children, (row: any) => {
        if (row) bodyRows.push(row);
      });
    }
  });

  const totalRows = bodyRows.length;
  const totalPages = Math.ceil(totalRows / PAGE_SIZE);
  const start = page * PAGE_SIZE;
  const visibleRows = bodyRows.slice(start, start + PAGE_SIZE);
  const needsPagination = totalRows > PAGE_SIZE;

  const copyTable = () => {
    // Build plain text of table for clipboard
    const el = document.createElement('div');
    const tableEl = document.createElement('table');
    el.appendChild(tableEl);
    // Just copy raw text content
    const rows: string[] = [];
    bodyRows.forEach((row: any) => {
      const cells: string[] = [];
      React.Children.forEach(row.props.children, (cell: any) => {
        cells.push(String(cell?.props?.children ?? ''));
      });
      rows.push(cells.join('\t'));
    });
    navigator.clipboard.writeText(rows.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 border border-gray-200 rounded-xl overflow-hidden bg-white">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {headRows && React.cloneElement(headRows as React.ReactElement, {
            className: 'bg-gray-50',
            children: React.Children.map((headRows as any).props.children, (tr: any) =>
              React.cloneElement(tr, {
                children: React.Children.map(tr.props.children, (th: any) =>
                  React.cloneElement(th, {
                    className: 'text-left px-4 py-2.5 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-200 whitespace-nowrap',
                  })
                ),
              })
            ),
          })}
          <tbody className="divide-y divide-gray-100">
            {visibleRows.map((row: any, i: number) =>
              React.cloneElement(row, {
                key: i,
                className: 'hover:bg-gray-50 transition-colors',
                children: React.Children.map(row.props.children, (td: any) =>
                  React.cloneElement(td, {
                    className: 'px-4 py-2 text-sm text-gray-700 whitespace-nowrap font-mono',
                  })
                ),
              })
            )}
          </tbody>
        </table>
      </div>
      {/* Footer with pagination */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <span>{totalRows} row{totalRows !== 1 ? 's' : ''}</span>
          <button onClick={copyTable} className="flex items-center gap-1 px-2 py-0.5 text-gray-400 hover:text-gray-600 rounded transition" title="Copy table">
            {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
        {needsPagination && (
          <div className="flex items-center gap-2">
            <span>{start + 1}–{Math.min(start + PAGE_SIZE, totalRows)} of {totalRows}</span>
            <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30 transition">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setPage(Math.min(totalPages - 1, page + 1))} disabled={page >= totalPages - 1}
              className="p-1 rounded hover:bg-gray-200 disabled:opacity-30 transition">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function CodeBlock({ className, children, ...props }: any) {
  const [copied, setCopied] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');

  if (!match) {
    // Inline code
    return <code className="px-1.5 py-0.5 bg-gray-100 text-pink-600 text-[13px] rounded font-mono" {...props}>{children}</code>;
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-gray-200 bg-gray-900">
      <div className="flex items-center justify-between px-4 py-1.5 bg-gray-800 text-xs">
        <span className="text-gray-400 uppercase tracking-wide">{lang || 'code'}</span>
        <button onClick={handleCopy} className="flex items-center gap-1 text-gray-400 hover:text-white transition">
          {copied ? <><Check className="w-3 h-3 text-green-400" /> Copied</> : <><Copy className="w-3 h-3" /> Copy</>}
        </button>
      </div>
      <pre className="px-4 py-3 overflow-x-auto text-sm leading-relaxed text-gray-100">
        <code className={className}>{code}</code>
      </pre>
    </div>
  );
}

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children }) => <PaginatedTable>{children}</PaginatedTable>,
        code: CodeBlock,
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
        ul: ({ children }) => <ul className="list-disc ml-5 mb-2 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal ml-5 mb-2 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        h1: ({ children }) => <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold mt-3 mb-2">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-bold mt-3 mb-1">{children}</h3>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-brand-300 pl-4 my-2 text-gray-600 italic">{children}</blockquote>
        ),
        hr: () => <hr className="my-4 border-gray-200" />,
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline hover:text-brand-700">{children}</a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
