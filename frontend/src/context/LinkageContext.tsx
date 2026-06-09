import React, { createContext, useContext, useState, ReactNode } from 'react';

interface LinkSource {
  ic?: string;
  name?: string | null;
  dob?: string | null;
  gender?: string | null;
  state?: string | null;
  district?: string | null;
  measure_date?: string | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  bmi?: number | null;
  waz?: number | null;
  haz?: number | null;
  baz?: number | null;
  source_type: string;
  dataset_id: string;
}

interface ConflictEntry {
  field: string;
  severity: 'hard' | 'soft' | 'strong';
  values: { source_type: string; value: string }[];
}

interface TimelineEntry {
  date: string;
  source_type: string;
  weight_kg: number | null;
  height_cm: number | null;
  bmi: number | null;
  waz: number | null;
  haz: number | null;
  baz: number | null;
}

interface LinkProfile {
  ic: string;
  name: string | null;
  dob: string | null;
  confidence: number;
  match_reasons: string[];
  sources: LinkSource[];
  conflicts: ConflictEntry[];
  profile?: {
    canonical: {
      ic?: string | null;
      name?: string | null;
      dob?: string | null;
      gender?: string | null;
      state?: string | null;
      district?: string | null;
    };
    timeline: TimelineEntry[];
  };
}

export interface LinkResult {
  total_groups: number;
  linked_groups: number;
  unlinked: number;
  datasets: Array<{
    dataset_id: string;
    filename: string;
    source_type: string | null;
    records: number;
    created_at?: string | null;
  }>;
  profiles: LinkProfile[];
  warning?: string;
}

interface LinkageContextType {
  linkageResult: LinkResult | null;
  setLinkageResult: (result: LinkResult | null) => void;
  clearLinkageResult: () => void;
}

const LinkageContext = createContext<LinkageContextType | undefined>(undefined);

export function LinkageProvider({ children }: { children: ReactNode }) {
  const [linkageResult, setLinkageResult] = useState<LinkResult | null>(null);

  const clearLinkageResult = () => {
    setLinkageResult(null);
  };

  return (
    <LinkageContext.Provider value={{ linkageResult, setLinkageResult, clearLinkageResult }}>
      {children}
    </LinkageContext.Provider>
  );
}

export function useLinkage() {
  const context = useContext(LinkageContext);
  if (context === undefined) {
    throw new Error('useLinkage must be used within a LinkageProvider');
  }
  return context;
}
