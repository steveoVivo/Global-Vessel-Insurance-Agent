import React, { createContext, useState, useContext } from 'react';

type ActivePanels = 'Selected_Country' | 'Custom_Risk';
interface PanelContextData {
  activePanel: ActivePanels,
  setActivePanel: (_: ActivePanels) => void
}

const defaultActivePanel: ActivePanels = 'Custom_Risk';

const PanelContext = createContext<PanelContextData>(null);

export const PanelProvider = ({ children }: any) => {
  const [activePanel, setActivePanel] = useState<ActivePanels>(defaultActivePanel);

  return (
    <PanelContext.Provider value={{ activePanel, setActivePanel }}>
      {children}
    </PanelContext.Provider>
  );
};

// Custom hook for easy consumption
export default function getPanelContext() {
  const context = useContext(PanelContext);
  if (!context) {
    throw new Error('getPanelContext must be used within a PanelProvider');
  }
  return context;
};