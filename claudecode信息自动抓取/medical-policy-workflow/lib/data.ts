// Server-side data loaders — fs.readFileSync runs at BUILD TIME only.
// Import this ONLY in Server Components (no 'use client' files).
import fs from 'node:fs';
import path from 'node:path';
import type { PolicyRecord, NewsRecord, DrugRecord, AcademicRecord, Module } from './types';

const DATA_ROOT = path.join(process.cwd(), 'data');

function readJson<T>(rel: string): T {
  const fullPath = path.join(DATA_ROOT, rel);
  try {
    return JSON.parse(fs.readFileSync(fullPath, 'utf-8')) as T;
  } catch {
    // Return empty array when file is missing — keeps build from crashing during scaffolding
    return [] as unknown as T;
  }
}

export function loadModuleData(
  industry: string,
  country: string,
  module: Module,
): PolicyRecord[] | NewsRecord[] | DrugRecord[] | AcademicRecord[] {
  const rel = `${industry}/${country}/${module}.json`;
  switch (module) {
    case 'policy_all':
    case 'policy_monthly':
      return readJson<PolicyRecord[]>(rel);
    case 'news_monthly':
      return readJson<NewsRecord[]>(rel);
    case 'drugs_monthly':
      return readJson<DrugRecord[]>(rel);
    case 'academic_monthly':
      return readJson<AcademicRecord[]>(rel);
    default:
      return [];
  }
}
