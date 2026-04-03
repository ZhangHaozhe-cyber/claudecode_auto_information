'use client';

import { useState, useMemo } from 'react';
import type { NewsRecord } from '@/lib/types';
import { TAG_PILL_COLORS } from '@/lib/constants';

interface NewsTimelineProps {
  data: NewsRecord[];
}

export function NewsTimeline({ data }: NewsTimelineProps) {
  const allTags = useMemo(
    () => Array.from(new Set(data.flatMap(n => n.tags))).sort(),
    [data],
  );
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const filtered = activeTag
    ? data.filter(n => n.tags.includes(activeTag))
    : data;

  return (
    <div>
      {/* Tag filter pills */}
      <div className="flex flex-wrap gap-2 mb-6">
        <button
          onClick={() => setActiveTag(null)}
          className={`tag-pill transition-opacity ${
            activeTag === null
              ? 'opacity-100 ring-2 ring-offset-1 ring-gray-400'
              : 'opacity-60 hover:opacity-90'
          }`}
          style={{ background: '#607D8B' }}
        >
          全部
        </button>
        {allTags.map(tag => (
          <button
            key={tag}
            onClick={() => setActiveTag(activeTag === tag ? null : tag)}
            className={`tag-pill transition-opacity ${
              activeTag === tag
                ? 'opacity-100 ring-2 ring-offset-1 ring-blue-400'
                : 'opacity-70 hover:opacity-100'
            }`}
            style={{ background: TAG_PILL_COLORS[tag] ?? '#607D8B' }}
          >
            {tag}
          </button>
        ))}
        <span className="self-center text-xs text-gray-400 ml-2">
          {filtered.length} 条
        </span>
      </div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-gray-200 dark:bg-gray-700" />

        <div className="space-y-4 ml-8">
          {filtered.length === 0 ? (
            <p className="text-gray-400 py-8">暂无简讯</p>
          ) : (
            filtered.map((item, i) => (
              <div key={i} className="news-card relative">
                {/* Timeline dot */}
                <div
                  className="absolute -left-[2.1rem] top-5 w-3 h-3 rounded-full border-2 border-white dark:border-gray-900"
                  style={{ background: TAG_PILL_COLORS[item.tags[0]] ?? '#1A73E8' }}
                />

                <div className="text-xs text-gray-400 mb-1">{item.date}</div>
                <div className="font-semibold text-gray-800 dark:text-gray-100 mb-2 leading-snug">
                  {item.title}
                </div>
                <div className="mb-2">
                  {item.tags.map(tag => (
                    <span
                      key={tag}
                      className="tag-pill"
                      style={{ background: TAG_PILL_COLORS[tag] ?? '#607D8B' }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                  {item.summary}
                </p>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
