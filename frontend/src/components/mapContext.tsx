import React, { createContext, useState, useContext } from 'react';
import { Map } from 'ol';

interface MapContextData {
  map: Map,
  setMap: any // TODO: Type this
}

// TODO: Come back, type this, recomment and restructure
const MapContext = createContext<MapContextData>(null);

export const MapProvider = ({ children }: any) => {
  const [map, setMap] = useState(null);

  return (
    <MapContext.Provider value={{ map, setMap }}>
      {children}
    </MapContext.Provider>
  );
};

// Custom hook for easy consumption
export default function getMapContext() {
  const context = useContext(MapContext);
  if (!context) {
    throw new Error('getMapContext must be used within a MapProvider');
  }
  return context;
};