import 'ol/ol.css';
import './App.css';

import { MapProvider } from './components/mapContext';
import { RiskProvider } from './components/riskContext';
import { SelectionProvider } from './components/selectionContext';
import { PanelProvider } from './components/panelContext';
import { TrendProvider } from './components/trendContext';
import MapComponent from './components/mapComponent';
import ControlPanelComponent from './components/controlPanelComponent';
import CustomriskPanelComponent from './components/customriskPanelComponent';

/**
 * Entry point for the entire project
 */
function App() {
  return (
    <MapProvider>
    <RiskProvider>
    <SelectionProvider>
    <PanelProvider>
    <TrendProvider>
      <h1>Global Vessel Insurance Agent</h1>
      <div className='app-main'>
        <MapComponent />
        <ControlPanelComponent />
      </div>
      <div className='custom-risk-bar'>
        <CustomriskPanelComponent />
      </div>
    </TrendProvider>
    </PanelProvider>
    </SelectionProvider>
    </RiskProvider>
    </MapProvider>
  );
}

export default App;
