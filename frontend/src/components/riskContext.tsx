import React, { createContext, useState, useRef, useContext } from 'react';
import { Map } from 'ol';

export type RiskName = 'Risk_A' | 'Risk_B' | 'Risk_C' | 'Risk_D' | 'Custom'; 
export type NumericRisk = [number, number, number, number];
interface RiskContextData {
  riskDistribution: NumericRisk,
  setDistribution: (_: RiskName) => void,
  setCustomDistribution: (_: NumericRisk) => void
}

// TODO: Come back, type this, recomment and restructure
const RiskContext = createContext<RiskContextData>(null);

export const RiskProvider = ({ children }: any) => {
  const [distribution, setDistribution] = useState<RiskName>('Risk_B');
  const customDistribution = useRef<NumericRisk>([0, 0, 0, 1]);
  const setCustomDistribution = (distribution: NumericRisk) => {customDistribution.current = distribution};

  // TODO: Find out what's causing this to update twice
  console.log('Updated');

  let riskDistribution: NumericRisk = null;
  switch (distribution) {
    case ('Risk_A'): riskDistribution = [1, 0, 0, 0]; break;
    case ('Risk_B'): riskDistribution = [0, 1, 0, 0]; break;
    case ('Risk_C'): riskDistribution = [0, 0, 1, 0]; break;
    case ('Risk_D'): riskDistribution = [0, 0, 0, 1]; break;
    default: riskDistribution = customDistribution.current;
  }


  return (
    <RiskContext.Provider value={{ riskDistribution, setDistribution, setCustomDistribution }}>
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