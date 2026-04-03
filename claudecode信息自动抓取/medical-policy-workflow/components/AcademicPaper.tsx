// Server Component — no 'use client' needed
// Uses native <details>/<summary> for expand/collapse (no JS hydration required)
import type { AcademicRecord } from '@/lib/types';

interface AcademicPaperProps {
  data: AcademicRecord[];
}

const KW_COLORS = [
  '#E8F0FE text-[#3730A3]',
  '#E6F4EA text-[#1E6832]',
  '#FCE8E6 text-[#C5221F]',
  '#F3E8FD text-[#7B1FA2]',
];

export function AcademicPaper({ data }: AcademicPaperProps) {
  if (data.length === 0) {
    return (
      <div className="py-16 text-center text-gray-400">
        <p className="text-4xl mb-3">📚</p>
        <p>暂无文献数据</p>
        <p className="text-sm mt-1">Phase 3 接入 PubMed / CNKI 数据后自动更新</p>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      {data.map((paper, i) => (
        <article
          key={i}
          className="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm
            border border-gray-100 dark:border-gray-700"
        >
          {/* Title */}
          <h2 className="mb-1">
            <a
              href={paper.url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="paper-title-link"
            >
              {paper.title}
            </a>
          </h2>

          {/* Meta */}
          <p className="paper-meta">
            {paper.authors} &nbsp;·&nbsp; <em>{paper.journal}</em>
            {paper.pub_date && (
              <span className="ml-2 not-italic text-gray-400">{paper.pub_date}</span>
            )}
          </p>

          {/* Keywords */}
          {paper.keywords?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {paper.keywords.map((kw, j) => {
                const colorClass = KW_COLORS[j % KW_COLORS.length];
                const [bg, fg] = colorClass.split(' ');
                return (
                  <span
                    key={kw}
                    className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium ${fg}`}
                    style={{ background: bg.replace('bg-', '').startsWith('#') ? bg.replace('bg-', '') : undefined }}
                  >
                    {kw}
                  </span>
                );
              })}
            </div>
          )}

          {/* Abstract — native HTML expand/collapse, no JS needed */}
          <details className="group">
            <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-600
              dark:hover:text-gray-200 select-none list-none flex items-center gap-1">
              <span className="group-open:hidden">▸ 查看摘要</span>
              <span className="hidden group-open:inline">▾ 收起摘要</span>
            </summary>
            <p className="mt-3 text-sm text-gray-600 dark:text-gray-300 leading-relaxed
              border-t border-gray-100 dark:border-gray-700 pt-3">
              {paper.abstract}
            </p>
          </details>
        </article>
      ))}
    </div>
  );
}
