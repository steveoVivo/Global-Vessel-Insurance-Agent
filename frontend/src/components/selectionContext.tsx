import React, { createContext, useState, useContext } from 'react';

interface CountrySelection {
  country: string,
  risk: [number, number, number, number, number],
  fleetSize: number
}

// TODO: Type the numberes as an array
interface SelectionContextData {
  currentCountry: string,
  currentRisk: [number, number, number, number, number],
  currentFleetSize: number
  setSelectedCountry: (_: CountrySelection) => void
}

// TODO: Come back, type this, recomment and restructure
const SelectionContext = createContext<SelectionContextData>(null);

export const SelectionProvider = ({ children }: any) => {
  const [selectedCountry, setSelectedCountry] = useState<CountrySelection>(null);

  const currentCountry = selectedCountry?.country;
  const currentRisk = selectedCountry?.risk
  const currentFleetSize = selectedCountry?.fleetSize;

  return (
    <SelectionContext.Provider value={{ currentCountry, currentRisk, currentFleetSize, setSelectedCountry}}>
      {children}
    </SelectionContext.Provider>
  );
};

export default function getSelectionContext() {
  const context = useContext(SelectionContext);
  if (!context) {
    throw new Error('getSelectioncontext must be used within a RiskProvider');
  }
  return context;
};