import React, { createContext, useState, useRef, useContext } from 'react';

export type RiskName = 'Accident_Risk' | 'Flag_Risk' | 'Event_Risk' | 'Investigation_Risk' | 'Trend_Risk' | 'Custom';
export type NumericRisk = [number, number, number, number, number];
interface RiskContextData {
  riskDistributionName: RiskName,
  riskDistribution: NumericRisk,
  setDistribution: (_: RiskName) => void,
  setCustomDistribution: (_: NumericRisk) => void
}

// TODO: Come back, type this, recomment and restructure
const RiskContext = createContext<RiskContextData>(null);

export const RiskProvider = ({ children }: any) => {
  const [distribution, setDistribution] = useState<RiskName>('Custom');
  const [customDistribution, setCustomDistribution] = useState<NumericRisk>([0.2, 0.2, 0.2, 0.2, 0.2]);
  // const customDistribution = useRef<NumericRisk>([0.2, 0.2, 0.2, 0.2, 0.2]);
  // const setCustomDistribution = (distribution: NumericRisk) => {customDistribution.current = distribution};

  // TODO: Find out what's causing this to update twice
  console.log('Updated');

  let riskDistribution: NumericRisk = null;
  switch (distribution) {
    case ('Accident_Risk'): riskDistribution = [1, 0, 0, 0, 0]; break;
    case ('Flag_Risk'): riskDistribution = [0, 1, 0, 0, 0]; break;
    case ('Event_Risk'): riskDistribution = [0, 0, 1, 0, 0]; break;
    case ('Investigation_Risk'): riskDistribution = [0, 0, 0, 1, 0]; break;
    case ('Trend_Risk'): riskDistribution = [0, 0, 0, 0, 1]; break;
    default: riskDistribution = customDistribution;
  }


  return (
    <RiskContext.Provider value={{ riskDistributionName: distribution, riskDistribution, setDistribution, setCustomDistribution }}>
      {children}
    </RiskContext.Provider>
  );
};

export default function getRiskContext() {
  const context = useContext(RiskContext);
  if (!context) {
    throw new Error('getRiskContext must be used within a RiskProvider');
  }
  return context;
};

export function RiskTypeToEnglishName(riskType: RiskName): string {
  switch (riskType) {
    case ('Accident_Risk'): return 'Accident Rate';
    case ('Flag_Risk'): return 'Flag Safety'
    case ('Event_Risk'): return 'Event Entropy';
    case ('Investigation_Risk'): return 'Investigation Rate';
    case ('Trend_Risk'): return 'Trend Slope';
  }
  return 'Custom';
} 