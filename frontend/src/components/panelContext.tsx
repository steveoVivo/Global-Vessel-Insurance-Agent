import React, { createContext, useState, useContext } from 'react';

// TODO: Revert to the old two panels on the bottom, or ONLY track 'Selected_Country' with a boolean
type ActivePanels = 'Selected_Country' | 'Custom_Risk';
interface PanelContextData {
  activePanel: ActivePanels,
  setActivePanel: (_: ActivePanels) => void
}

const defaultActivePanel: ActivePanels = 'Custom_Risk';

const PanelContext = createContext<PanelContextData>(null);

/**
 * This is a legacy item. It should be removed in future iterations, or we should return to the two bottom panel format.
 * @param {any} children - Standard React structure to pass HTML through props
 * @desc React - Context
 */
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