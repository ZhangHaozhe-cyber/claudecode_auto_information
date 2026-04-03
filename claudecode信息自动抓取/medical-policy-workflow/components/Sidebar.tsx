'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from './ThemeProvider';

const NAV_TREE = [
  {
    id: 'biomedicine',
    label: '生物医药',
    countries: [
      {
        id: 'china', label: '中国', active: true,
        modules: [
          { id: 'policy_all',       label: '产业政策（全部）' },
          { id: 'policy_monthly',   label: '产业政策（月度）' },
          { id: 'news_monthly',     label: '行业新闻' },
          { id: 'drugs_monthly',    label: '药物资讯' },
          { id: 'academic_monthly', label: '文献总结' },
        ],
      },
      { id: 'usa',     label: '美国',   active: false, modules: [] },
      { id: 'japan',   label: '日本',   active: false, modules: [] },
      { id: 'korea',   label: '韩国',   active: false, modules: [] },
      { id: 'germany', label: '德国',   active: false, modules: [] },
      { id: 'uk',      label: '英国',   active: false, modules: [] },
      { id: 'france',  label: '法国',   active: false, modules: [] },
      { id: 'swiss',   label: '瑞士',   active: false, modules: [] },
    ],
  },
  {
    id: 'biomanufacturing',
    label: '生物制造',
    countries: [
      {
        id: 'china', label: '中国', active: true,
        modules: [
          { id: 'policy_all',       label: '产业政策' },
          { id: 'news_monthly',     label: '行业新闻' },
          { id: 'academic_monthly', label: '文献总结' },
        ],
      },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(true);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleSection = (key: string) =>
    setCollapsed(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <aside
      className={`
        flex-shrink-0 h-full flex flex-col
        bg-white dark:bg-gray-900
        border-r border-gray-200 dark:border-gray-700
        transition-all duration-200
        ${open ? 'w-60' : 'w-12'}
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gray-200 dark:border-gray-700">
        {open && (
          <span className="font-semibold text-sm text-gray-800 dark:text-gray-100 truncate">
            医药产业平台
          </span>
        )}
        <button
          onClick={() => setOpen(o => !o)}
          className="p-1.5 rounded text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 ml-auto"
          aria-label="Toggle sidebar"
        >
          {open ? '‹' : '›'}
        </button>
      </div>

      {/* Navigation */}
      {open && (
        <nav className="flex-1 overflow-y-auto py-2 text-sm">
          {NAV_TREE.map(industry => {
            const isCollapsed = collapsed[industry.id];
            return (
              <div key={industry.id} className="mb-2">
                <button
                  onClick={() => toggleSection(industry.id)}
                  className="w-full flex items-center gap-1.5 px-3 py-1.5
                    text-xs font-semibold text-gray-400 dark:text-gray-500
                    uppercase tracking-wider hover:text-gray-600 dark:hover:text-gray-300"
                >
                  <span>{isCollapsed ? '▸' : '▾'}</span>
                  {industry.label}
                </button>

                {!isCollapsed && industry.countries.map(country => (
                  <div key={country.id} className="ml-1 mb-1">
                    <div className={`px-4 py-0.5 text-xs font-medium flex items-center gap-1.5 ${
                      country.active
                        ? 'text-gray-600 dark:text-gray-300'
                        : 'text-gray-300 dark:text-gray-600'
                    }`}>
                      {country.label}
                      {!country.active && (
                        <span className="text-[10px] bg-gray-100 dark:bg-gray-800
                          text-gray-400 px-1.5 py-0.5 rounded-full">
                          即将开放
                        </span>
                      )}
                    </div>

                    {country.active && country.modules.map(mod => {
                      const href = `/${industry.id}/${country.id}/${mod.id}`;
                      const isActive =
                        pathname === href || pathname === `${href}/`;
                      return (
                        <Link
                          key={mod.id}
                          href={href}
                          className={`block px-5 py-1.5 rounded-md mx-2 my-0.5
                            transition-colors duration-100 text-sm
                            ${isActive
                              ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium'
                              : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200'
                            }`}
                        >
                          {mod.label}
                        </Link>
                      );
                    })}
                  </div>
                ))}
              </div>
            );
          })}
        </nav>
      )}

      {/* Footer: dark mode toggle */}
      {open && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-2">
          <button
            onClick={toggle}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs
              text-gray-500 dark:text-gray-400 rounded hover:bg-gray-100
              dark:hover:bg-gray-800"
          >
            {theme === 'light' ? '🌙' : '☀️'}
            {theme === 'light' ? '深色模式' : '浅色模式'}
          </button>
        </div>
      )}
    </aside>
  );
}
