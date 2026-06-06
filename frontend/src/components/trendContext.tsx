import React, { createContext, useContext, useEffect, useState } from 'react';

export interface YearlyPoint {
  year: number;
  accident_rate: number;
  accident_count: number;
  exposure: number;
  has_fleet_data: boolean;
}

export interface MonthlyPoint {
  date: string;
  year: number;
  month: number;
  accident_rate: number;
  accident_count: number;
  exposure: number;
  has_fleet_data: boolean;
}

export interface PredictedYearlyPoint {
  year: number;
  accident_rate: number;
}

export interface FlagTrend {
  flag: string;
  flag_key: string;
  yearly: YearlyPoint[];
  monthly: MonthlyPoint[];
  predicted_yearly: PredictedYearlyPoint[];
}

interface TrendContextData {
  trendByFlag: Map<string, FlagTrend>;
  loading: boolean;
}

const TrendContext = createContext<TrendContextData>({ trendByFlag: new Map(), loading: true });

export const TrendProvider = ({ children }: { children: React.ReactNode }) => {
  const [trendByFlag, setTrendByFlag] = useState<Map<string, FlagTrend>>(new Map());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/trend')
      .then(r => r.json())
      .then((data: { data: FlagTrend[] }) => {
        const map = new Map<string, FlagTrend>();
        for (const entry of data.data) {
          map.set(entry.flag, entry);
          map.set(entry.flag_key, entry);
        }
        setTrendByFlag(map);
      })
      .catch(err => console.error('Failed to load trend data:', err))
      .finally(() => setLoading(false));
  }, []);

  return (
    <TrendContext.Provider value={{ trendByFlag, loading }}>
      {children}
    </TrendContext.Provider>
  );
};

export default function getTrendContext() {
  return useContext(TrendContext);
}
