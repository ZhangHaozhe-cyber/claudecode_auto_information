'use client';

import { useState, useMemo } from 'react';
import type { DrugRecord } from '@/lib/types';
import { PHASES, PHASE_COLORS } from '@/lib/constants';

interface DrugKanbanProps {
  data: DrugRecord[];
}

export function DrugKanban({ data }: DrugKanbanProps) {
  const institutions = useMemo(
    () => Array.from(new Set(data.map(d => d.institution))).sort(),
    [data],
  );
  const [phaseFilter, setPhaseFilter] = useState<string[]>([...PHASES]);
  const [instFilter, setInstFilter] = useState<string>('全部');

  const togglePhase = (p: string) =>
    setPhaseFilter(prev =>
      prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p],
    );

  const filtered = useMemo(
    () =>
      data.filter(
        d =>
          phaseFilter.includes(d.current_phase) &&
          (instFilter === '全部' || d.institution === instFilter),
      ),
    [data, phaseFilter, instFilter],
  );

  // Metrics per phase
  const phaseCounts = useMemo(
    () =>
      Object.fromEntries(
        PHASES.map(p => [p, data.filter(d => d.current_phase === p).length]),
      ),
    [data],
  );

  return (
    <div>
      {/* Phase metrics */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {PHASES.map(phase => (
          <button
            key={phase}
            onClick={() => togglePhase(phase)}
            className={`rounded-xl p-3 text-center border-2 transition-all ${
              phaseFilter.includes(phase)
                ? 'border-transparent shadow-sm'
                : 'border-gray-200 dark:border-gray-700 opacity-40'
            }`}
            style={
              phaseFilter.includes(phase)
                ? { background: PHASE_COLORS[phase] + '22', borderColor: PHASE_COLORS[phase] }
                : undefined
            }
          >
            <div
              className="phase-badge mb-1 w-full justify-center flex"
              style={{ background: PHASE_COLORS[phase] }}
            >
              {phase}
            </div>
            <div className="text-2xl font-bold text-gray-800 dark:text-gray-100">
              {phaseCounts[phase] ?? 0}
            </div>
            <div className="text-[11px] text-gray-400">个药物</div>
          </button>
        ))}
      </div>

      {/* Institution filter */}
      <div className="flex gap-3 mb-4 items-center">
        <label className="text-sm text-gray-500">机构：</label>
        <select
          value={instFilter}
          onChange={e => setInstFilter(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700
            bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200
            focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          <option value="全部">全部</option>
          {institutions.map(inst => (
            <option key={inst} value={inst}>{inst}</option>
          ))}
        </select>
        <span className="text-xs text-gray-400">{filtered.length} 个药物</span>
      </div>

      {/* Drug list */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {filtered.length === 0 ? (
          <p className="text-gray-400 col-span-3 py-8">暂无数据</p>
        ) : (
          filtered.map((drug, i) => (
            <div
              key={i}
              className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm
                border border-gray-100 dark:border-gray-700 hover:shadow-md
                transition-shadow duration-200"
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="font-semibold text-gray-800 dark:text-gray-100 text-sm leading-snug">
                  {drug.drug_name}
                </h3>
                <span
                  className="phase-badge flex-shrink-0"
                  style={{ background: PHASE_COLORS[drug.current_phase] }}
                >
                  {drug.current_phase}
                </span>
              </div>
              <div className="space-y-1 text-xs text-gray-500 dark:text-gray-400">
                <div>
                  <span className="font-medium text-gray-600 dark:text-gray-300">机构：</span>
                  {drug.institution}
                </div>
                <div>
                  <span className="font-medium text-gray-600 dark:text-gray-300">靶点：</span>
                  {drug.target}
                </div>
                <div>
                  <span className="font-medium text-gray-600 dark:text-gray-300">日期：</span>
                  {drug.event_date}
                </div>
                {drug.notes && (
                  <p className="mt-2 text-gray-400 leading-relaxed">{drug.notes}</p>
                )}
              </div>
              {drug.source_url && (
                <a
                  href={drug.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-block text-[11px] text-blue-500 hover:underline"
                >
                  数据来源 ↗
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
