import React, { createContext, useState, useRef, useContext } from 'react';

export type RiskName = 'Event_Risk' | 'Ship_Type_Risk' | 'Open_Sea_Risk' | 'Fleet_Volatility_Risk' | 'Custom';
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
  const [customDistribution, setCustomDistribution] = useState<NumericRisk>([1/4, 1/4, 1/4, 1/4]);

  // TODO: Find out what's causing this to update twice
  // console.log('Updated');

  let riskDistribution: NumericRisk = null;
  switch (distribution) {
    case ('Event_Risk'): riskDistribution = [1, 0, 0, 0]; break;
    case ('Ship_Type_Risk'): riskDistribution = [0, 1, 0, 0]; break;
    case ('Open_Sea_Risk'): riskDistribution = [0, 0, 1, 0]; break;
    case ('Fleet_Volatility_Risk'): riskDistribution = [0, 0, 0, 1]; break;
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

export function riskTypeToEnglishName(riskType: RiskName): string {
  switch (riskType) {
    case ('Event_Risk'): return 'Event Entropy';
    case ('Ship_Type_Risk'): return 'Ship Type';
    case ('Open_Sea_Risk'): return 'Open Sea';
    case ('Fleet_Volatility_Risk'): return 'Fleet Volatility';
  }
  return 'Custom';
}
