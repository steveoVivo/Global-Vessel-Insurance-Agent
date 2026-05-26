import React, { createContext, useState, useRef, useContext } from 'react';

// TODO: You need a type for country na,e
interface SelectionContextData {
  currentCountry: string,
  setCurrentCountry: (_: string) => void
}

// TODO: Come back, type this, recomment and restructure
const SelectionContext = createContext<SelectionContextData>(null);

export const SelectionProvider = ({ children }: any) => {
  const [currentCountry, setCurrentCountry] = useState<string>(null);

  return (
    <SelectionContext.Provider value={{ currentCountry, setCurrentCountry }}>
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