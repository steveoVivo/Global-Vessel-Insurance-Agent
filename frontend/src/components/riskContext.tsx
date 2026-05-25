import React, { createContext, useState, useRef, useContext } from 'react';

export type RiskName = 'Accident_Risk' | 'Flag_Risk' | 'Severity_Risk' | 'Ship_Risk' | 'Custom'; 
export type NumericRisk = [number, number, number, number];
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
  const [customDistribution, setCustomDistribution] = useState<NumericRisk>([0.25, 0.25, 0.25, 0.25]);
  // const customDistribution = useRef<NumericRisk>([0.25, 0.25, 0.25, 0.25]);
  // const setCustomDistribution = (distribution: NumericRisk) => {customDistribution.current = distribution};

  // TODO: Find out what's causing this to update twice
  console.log('Updated');

  let riskDistribution: NumericRisk = null;
  switch (distribution) {
    case ('Accident_Risk'): riskDistribution = [1, 0, 0, 0]; break;
    case ('Flag_Risk'): riskDistribution = [0, 1, 0, 0]; break;
    case ('Severity_Risk'): riskDistribution = [0, 0, 1, 0]; break;
    case ('Ship_Risk'): riskDistribution = [0, 0, 0, 1]; break;
    default: riskDistribution = customDistribution;
  }


  return (
    <RiskContext.Provider value={{ riskDistributionName: distribution, riskDistribution, setDistribution, setCustomDistribution }}>
      {children}
    </RiskContext.Provider>
  );
};

export default function getRiskContext () {
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
    case ('Severity_Risk'): return 'Severity';
    case ('Ship_Risk'): return 'Ship Type';
  }
  return 'Custom';
} 