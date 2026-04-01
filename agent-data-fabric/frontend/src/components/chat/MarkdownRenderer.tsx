import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChevronLeft, ChevronRight, Copy, Check, ChevronDown, ChevronUp, Table2, Code2, BarChart3 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const PAGE_SIZE = 10;
const CHART_COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#818cf8', '#4f46e5', '#7c3aed', '#5b21b6'];

function tryBuildChartData(headRows: React.ReactNode, bodyRows: React.ReactElement[]): { labels: string[]; data: Record<string, any>[] } | null {
  if (bodyRows.length < 2 || bodyRows.length > 50) return null;
  // Extract column headers
  const headers: string[] = [];
  if (headRows) {
    React.Children.forEach((headRows as any).props.children, (tr: any) => {
      React.Children.forEach(tr.props.children, (th: any) => {
        headers.push(String(th?.props?.children ?? ''));
      });
    });
  }
  if (headers.length < 2) return null;

  // Extract rows
  const rows: Record<string, any>[] = [];
  let hasNumeric = false;
  bodyRows.forEach((row: any) => {
    const cells: string[] = [];
    React.Children.forEach(row.props.children, (cell: any) => {
      cells.push(String(cell?.props?.children ?? ''));
    });
    const obj: Record<string, any> = {};
    headers.forEach((h, i) => {
      const val = cells[i] || '';
      const num = Number(val.replace(/,/g, ''));
      if (!isNaN(num) && val.trim() !== '' && i > 0) {
        obj[h] = num;
        hasNumeric = true;
      } else {
        obj[h] = val;
      }
    });
    rows.push(obj);
  });

  if (!hasNumeric) return null;
  return { labels: headers, data: rows };
}

function PaginatedTable({ children }: { children: React.ReactNode }) {
  const [page, setPage] = useState(0);
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [showChart, setShowChart] = useState(false);

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
  const chartData = tryBuildChartData(headRows, bodyRows);

  const copyTable = () => {
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
      {/* Header bar — always visible */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-50 border-b border-gray-200 text-xs text-gray-500">
        <button onClick={() => setCollapsed(!collapsed)} className="flex items-center gap-1.5 hover:text-gray-700 transition">
          {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          <Table2 className="w-3.5 h-3.5 text-brand-500" />
          <span className="font-medium">{totalRows} row{totalRows !== 1 ? 's' : ''}</span>
        </button>
        <div className="flex items-center gap-2">
          {chartData && (
            <button onClick={() => setShowChart(!showChart)}
              className={`flex items-center gap-1 px-2 py-0.5 rounded transition ${showChart ? 'bg-brand-100 text-brand-700' : 'text-gray-400 hover:text-gray-600'}`}
              title="Toggle chart">
              <BarChart3 className="w-3 h-3" />
            </button>
          )}
          <button onClick={copyTable} className="flex items-center gap-1 px-2 py-0.5 text-gray-400 hover:text-gray-600 rounded transition" title="Copy table">
            {copied ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* Chart view */}
      {showChart && chartData && !collapsed && (
        <div className="px-4 py-3 border-b border-gray-100">
          <ResponsiveContainer width="100%" height={Math.min(300, 50 + chartData.data.length * 25)}>
            <BarChart data={chartData.data} layout="horizontal" margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey={chartData.labels[0]} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
              {chartData.labels.slice(1).filter(l => typeof chartData.data[0]?.[l] === 'number').map((key, i) => (
                <Bar key={key} dataKey={key} fill={CHART_COLORS[i % CHART_COLORS.length]} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Table content — collapsible */}
      {!collapsed && (
        <>
          <div className="overflow-x-auto scrollbar-thin">
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
          {needsPagination && (
            <div className="flex items-center justify-end px-4 py-1.5 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
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
            </div>
          )}
        </>
      )}
    </div>
  );
}

function CodeBlock({ className, children, ...props }: any) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1] : '';
  const code = String(children).replace(/\n$/, '');
  const isSql = lang === 'sql';

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
        <button onClick={() => setCollapsed(!collapsed)} className="flex items-center gap-1.5 text-gray-400 hover:text-white transition">
          {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {isSql && <Code2 className="w-3 h-3 text-blue-400" />}
          <span className="uppercase tracking-wide">{lang || 'code'}</span>
          {isSql && collapsed && <span className="text-gray-500 ml-1 normal-case tracking-normal">{code.split('\n').length} lines</span>}
        </button>
        <button onClick={handleCopy} className="flex items-center gap-1 text-gray-400 hover:text-white transition">
          {copied ? <><Check className="w-3 h-3 text-green-400" /> Copied</> : <><Copy className="w-3 h-3" /> Copy</>}
        </button>
      </div>
      {!collapsed && (
        <pre className="px-4 py-3 overflow-x-auto scrollbar-thin text-sm leading-relaxed text-gray-100">
          <code className={className}>{code}</code>
        </pre>
      )}
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
