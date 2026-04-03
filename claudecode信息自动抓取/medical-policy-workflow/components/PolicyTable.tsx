'use client';

import { useState, useMemo } from 'react';
import type { PolicyRecord } from '@/lib/types';
import { DEPT_COLORS, NHSA_COL_MAP } from '@/lib/constants';

interface PolicyTableProps {
  data: PolicyRecord[];
}

export function PolicyTable({ data }: PolicyTableProps) {
  const [keyword, setKeyword] = useState('');
  const [deptFilter, setDeptFilter] = useState<string>('全部');

  const departments = useMemo(
    () => ['全部', ...Array.from(new Set(data.map(r => r.department))).sort()],
    [data],
  );

  const filtered = useMemo(() => {
    let rows = data;
    if (deptFilter !== '全部') rows = rows.filter(r => r.department === deptFilter);
    if (keyword.trim()) {
      const kw = keyword.trim().toLowerCase();
      rows = rows.filter(r => r.title.toLowerCase().includes(kw));
    }
    return rows;
  }, [data, keyword, deptFilter]);

  function downloadCsv() {
    const headers = ['发布日期', '标题', '发文部门', '政策类型', '链接'];
    const rows = filtered.map(r => [
      r.pub_date,
      `"${r.title.replace(/"/g, '""')}"`,
      r.department,
      r.policy_type ?? '',
      r.link,
    ]);
    const csv = '\uFEFF' + [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `policies_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <input
          type="text"
          placeholder="标题关键词搜索…"
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          className="flex-1 min-w-48 px-3 py-1.5 text-sm rounded-lg border
            border-gray-200 dark:border-gray-700
            bg-white dark:bg-gray-800
            text-gray-800 dark:text-gray-100
            placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <select
          value={deptFilter}
          onChange={e => setDeptFilter(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700
            bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200
            focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {departments.map(d => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
        <button
          onClick={downloadCsv}
          className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700
            text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800
            transition-colors"
        >
          ↓ 导出 CSV
        </button>
        <span className="self-center text-xs text-gray-400">
          共 {filtered.length} 条
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-gray-100 dark:border-gray-800">
        <table className="data-table">
          <thead>
            <tr>
              <th className="w-24">日期</th>
              <th>标题</th>
              <th className="w-28">部门</th>
              <th className="w-24">类型</th>
              <th className="w-16 text-center">链接</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-gray-400">
                  暂无数据
                </td>
              </tr>
            ) : (
              filtered.map((row, i) => {
                const deptColor = DEPT_COLORS[row.department] ?? '#607D8B';
                const colLabel = row.source_col
                  ? NHSA_COL_MAP[row.source_col] ?? row.source_col
                  : null;
                return (
                  <tr key={i}>
                    <td className="text-xs text-gray-400 whitespace-nowrap">
                      {row.pub_date}
                    </td>
                    <td>
                      <a
                        href={row.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-800 dark:text-gray-100 hover:text-blue-600
                          dark:hover:text-blue-300 hover:underline leading-snug"
                      >
                        {row.title}
                      </a>
                      {colLabel && (
                        <span className="ml-2 text-[11px] text-gray-400">
                          [{colLabel}]
                        </span>
                      )}
                      {row.fwzh && (
                        <span className="ml-1 text-[11px] text-gray-400">
                          {row.fwzh}
                        </span>
                      )}
                    </td>
                    <td>
                      <span
                        className="inline-block px-1.5 py-0.5 rounded text-[11px] font-medium text-white"
                        style={{ background: deptColor }}
                      >
                        {row.department}
                      </span>
                    </td>
                    <td className="text-xs text-gray-500">
                      {row.policy_type ?? '—'}
                    </td>
                    <td className="text-center">
                      <a
                        href={row.link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:text-blue-700 text-xs"
                      >
                        原文 ↗
                      </a>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
