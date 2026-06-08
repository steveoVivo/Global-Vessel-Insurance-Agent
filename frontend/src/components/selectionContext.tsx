import React, { createContext, useState, useContext } from 'react';

interface CountrySelection {
  country: string,
  countryCode: string | null,
  risk: [number, number, number, number, number, number],
  fleetSize: number
}

interface SelectionContextData {
  currentCountry: string,
  currentCountryCode: string | null,
  currentRisk: [number, number, number, number, number, number],
  currentFleetSize: number
  setSelectedCountry: (_: CountrySelection) => void
}

const SelectionContext = createContext<SelectionContextData>(null);

/**
 * Context that tracks the currently selected country
 * Set by the mapComponent, needed by the circleHook, accidentListComponent, controlPanelComponent and countryPanelComponent
 * @param {any} children - Standard React structure to pass HTML through props 
 * @desc React - Context
 */
export const SelectionProvider = ({ children }: any) => {
  const [selectedCountry, setSelectedCountry] = useState<CountrySelection>(null);

  const currentCountry = selectedCountry?.country;
  const currentCountryCode = selectedCountry?.countryCode ?? null;
  const currentRisk = selectedCountry?.risk;
  const currentFleetSize = selectedCountry?.fleetSize;

  return (
    <SelectionContext.Provider value={{ currentCountry, currentCountryCode, currentRisk, currentFleetSize, setSelectedCountry }}>
      {children}
    </SelectionContext.Provider>
  );
};

export default function getSelectionContext() {
  const context = useContext(SelectionContext);
  if (!context) {
    throw new Error('getSelectionContext must be used within a SelectionProvider');
  }
  return context;
};
