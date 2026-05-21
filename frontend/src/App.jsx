import { useState, useEffect, useRef } from 'react';
import { Map, View } from 'ol';
import { OSM } from 'ol/source';
import TileLayer from 'ol/layer/Tile';

import reactLogo from './assets/react.svg';
import viteLogo from './assets/vite.svg';
import heroImg from './assets/hero.png';
import './App.css';

// Necessary to import in the same place as the map, otherwise controls will look weird
import 'ol/ol.css';
// Imports that should eventually be moved into a functionality file
import Feature from 'ol/Feature';
import Point from 'ol/geom/Point';
import { fromLonLat } from 'ol/proj';
import { Style, Circle, Fill, Stroke } from 'ol/style';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';


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


    // -------> Create the map <-------
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


    // -------> TEST: Render circles on the map <-------
    // TODO: Move this to the top of the useEffect
    if (!mapRef.current) return;

    // SF, Oakland, and Twin Peaks. I got the exact co-ordinates from Google Gemini
    const testCoordinates = [
      [-122.4194, 37.7749],
      [-122.2711, 37.8044],
      [-122.4467, 37.7337]
    ];

    // TODO: Is this the best way of doing this? Not a huge fan of literally drawing images
    const testCircles = testCoordinates.map(coordinate => {
      return new Feature({
        geometry: new Point(fromLonLat(coordinate))
      });
    });

    const circleStyles = new Style({
      image: new Circle({
        radius: 20,
        fill: new Fill({ color: 'rgba(160, 0, 0, 0.65)' }),
        stroke: new Stroke({ color: 'rgb(160, 0, 0)', width: 3 })
      })
    });

    const circleSource = new VectorSource({
      features: testCircles,
    });

    const circleLayer = new VectorLayer({
      source: circleSource,
      style: circleStyles,
    });

    openLayersMap.addLayer(circleLayer);


    // TODO: This is useless for now
    setMap(openLayersMap);

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
