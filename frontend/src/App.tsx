import { useState, useEffect } from 'react';

// TODO: Do I need these?
import reactLogo from './assets/react.svg';
import viteLogo from './assets/vite.svg';
import heroImg from './assets/hero.png';
// TODO: Go through the whole app and see where you can cross off these imports
import './App.css';


// Necessary to import in the same place as the map, otherwise controls will look weird
import 'ol/ol.css';

import { MapProvider } from './components/mapContext';
import { RiskProvider } from './components/riskContext';
import { SelectionProvider } from './components/selectionContext';
import MapComponent from './components/mapComponent';
import ControlPanelComponent from './components/controlPanelComponent';

// TODO: Just for later, check and make sure you're not pulling a `| null` anywhere anymore
// TODO: I'm sorry, you need to go over all code and change every tab length to either 2 spaces or 4 spaces

// const starterText = "If you see this message, your React app is working. This message should be replaced momentarily.";

function App() {
  return (
    <MapProvider>
    <RiskProvider>
    <SelectionProvider>
      <h1> Global Vessel Insurance Agent </h1>
      <div style={{ display: 'flex', flexDirection: 'column', flexGrow: 1, height: '100%', minHeight:'10px'}}>
        <MapComponent />
        <ControlPanelComponent />
      </div>
    </SelectionProvider>
    </RiskProvider>
    </MapProvider>
  )
}

export default App
