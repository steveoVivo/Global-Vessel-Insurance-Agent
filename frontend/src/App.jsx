import { useState, useEffect, useRef } from 'react'
import { Map, View } from 'ol'
import { OSM } from 'ol/source'
import TileLayer from 'ol/layer/Tile'

import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

const starterText = "If you see this message, your React app is working. This message should be replaced momentarily.";

const ucDavisCoordinates = [-93703952.94088145, 4656009.537393207];
const ucDavisZoom = 14.165;

function App() {
  // TODO: The following 3 should use templates `HTMLDivElement, string, Map`.
  //   For some reason it's whining when I use em
  const mapRef = useRef(null);

  const [data, setData] = useState(starterText);
  const [map, setMap] = useState(null)

  useEffect(() => {
    // -------> Retrieve Test Data <-------

    // '/api' retrieves data from the Vite Proxy
    fetch('/api/data')
      .then(res => res.json())
      .then(data => setData(data.message))
      .catch(err => console.error(err))

    // -------> Retrieve Map Data <-------
    const openLayersMap = new Map({
      target: mapRef.current,
      layers: [
        new TileLayer({
          source: new OSM()
        })
      ],
      view: new View({
        center: ucDavisCoordinates,
        zoom: ucDavisZoom
      })
    });

    // TODO: For some reason, this renders a second map
    // setMap(openLayersMap);

    // Un-Render the map when App is un-rendered
    return () => openLayersMap.setTarget(undefined);
  }, []);

  return (
    <div style={{display: 'grid', placeItems: 'center'}}>
      <div> {data} </div>
      <div ref={mapRef} style={{width: '90%', height: 600}}></div>
    </div>
  )
}

export default App
