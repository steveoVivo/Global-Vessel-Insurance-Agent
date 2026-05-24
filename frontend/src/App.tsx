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
import MapComponent from './components/mapComponent';

// TODO: Just for later, check and make sure you're not pulling a `| null` anywhere anymore
// TODO: I'm sorry, you need to go over all code and change every tab length to either 2 spaces or 4 spaces

const starterText = "If you see this message, your React app is working. This message should be replaced momentarily.";

function App() {
  const [data, setData] = useState<string>(starterText);

  useEffect(() => {
    // -------> Retrieve Test Data <-------
    // '/api' retrieves data from the Vite Proxy
    fetch('/api/test')
      .then(res => res.json())
      .then(data => setData(data.message))
      .catch(err => console.error(err))


    // Un-Render the map when App is un-rendered
    return;
  }, []);

  return (
    <MapProvider>
    <RiskProvider>
      <div style={{display: 'grid', placeItems: 'center'}}>
        <div> {data} </div>
        <MapComponent />
      </div>
    </RiskProvider>
    </MapProvider>
  )
}

export default App
