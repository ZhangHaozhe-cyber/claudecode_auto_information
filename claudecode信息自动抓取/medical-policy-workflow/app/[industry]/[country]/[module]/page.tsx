import { loadModuleData } from '@/lib/data';
import { MODULE_LABELS, INDUSTRY_LABELS, COUNTRY_LABELS } from '@/lib/constants';
import { PolicyTable } from '@/components/PolicyTable';
import { NewsTimeline } from '@/components/NewsTimeline';
import { DrugKanban } from '@/components/DrugKanban';
import { AcademicPaper } from '@/components/AcademicPaper';
import type {
  PolicyRecord,
  NewsRecord,
  DrugRecord,
  AcademicRecord,
  Module,
} from '@/lib/types';

// ── Static params — must enumerate every valid route ─────────────────────────
// With output:'export', Next.js pre-renders exactly these paths.
// Adding a new industry/country/module requires updating this list AND
// running python scripts/auto_pipeline.py to generate the corresponding JSON.

export function generateStaticParams() {
  return [
    { industry: 'biomedicine',      country: 'china', module: 'policy_all' },
    { industry: 'biomedicine',      country: 'china', module: 'policy_monthly' },
    { industry: 'biomedicine',      country: 'china', module: 'news_monthly' },
    { industry: 'biomedicine',      country: 'china', module: 'drugs_monthly' },
    { industry: 'biomedicine',      country: 'china', module: 'academic_monthly' },
    { industry: 'biomanufacturing', country: 'china', module: 'policy_all' },
    { industry: 'biomanufacturing', country: 'china', module: 'news_monthly' },
    { industry: 'biomanufacturing', country: 'china', module: 'academic_monthly' },
  ];
}

// ── Page component (Server Component) ────────────────────────────────────────
// params is a Promise in Next.js 15 App Router — must be awaited

type PageProps = {
  params: Promise<{ industry: string; country: string; module: string }>;
};

export default async function ModulePage({ params }: PageProps) {
  const { industry, country, module } = await params;

  const data = loadModuleData(industry, country, module as Module);

  const industryLabel = INDUSTRY_LABELS[industry] ?? industry;
  const countryLabel  = COUNTRY_LABELS[country] ?? country;
  const moduleLabel   = MODULE_LABELS[module] ?? module;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Breadcrumb header */}
      <div className="mb-6">
        <nav className="text-xs text-gray-400 mb-1">
          {industryLabel} / {countryLabel} / {moduleLabel}
        </nav>
        <h1 className="text-xl font-semibold text-gray-800 dark:text-gray-100">
          {moduleLabel}
        </h1>
        <p className="text-sm text-gray-400 mt-0.5">
          {(data as unknown[]).length} 条记录
        </p>
      </div>

      {/* Render the right component based on module */}
      {(module === 'policy_all' || module === 'policy_monthly') && (
        <PolicyTable data={data as PolicyRecord[]} />
      )}
      {module === 'news_monthly' && (
        <NewsTimeline data={data as NewsRecord[]} />
      )}
      {module === 'drugs_monthly' && (
        <DrugKanban data={data as DrugRecord[]} />
      )}
      {module === 'academic_monthly' && (
        <AcademicPaper data={data as AcademicRecord[]} />
      )}
    </div>
  );
}
