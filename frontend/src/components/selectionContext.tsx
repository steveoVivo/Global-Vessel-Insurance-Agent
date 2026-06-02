import React, { createContext, useState, useContext } from 'react';

// TODO: Type the numberes as an array
// TODO: You need a type for country na,e
interface SelectionContextData {
  currentCountry: string,
  setCurrentCountry: (_: string) => void,
  currentRisk: [number, number, number, number, number],
  setCurrentRisk: (_: [number, number, number, number, number]) => void
}

// TODO: Come back, type this, recomment and restructure
const SelectionContext = createContext<SelectionContextData>(null);

export const SelectionProvider = ({ children }: any) => {
  const [currentCountry, setCurrentCountry] = useState<string>(null);
  const [currentRisk, setCurrentRisk] = useState<[number, number, number, number, number]>(null);

  return (
    <SelectionContext.Provider value={{ currentCountry, setCurrentCountry, currentRisk, setCurrentRisk}}>
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