import { useEffect, useRef } from 'react';
import { Map, View } from 'ol';
import { OSM } from 'ol/source';
import TileLayer from 'ol/layer/Tile';

// Necessary to import in the same place as the map, otherwise controls will look weird
import 'ol/ol.css';

import getMapContext from './mapContext';

import circleHook from './circleHook';

const ucDavisCoordinates = [-93703952.94088145, 4656009.537393207];
const ucDavisZoom = 14.165;

function MapComponent() {
  const mapRef = useRef<HTMLDivElement>(null);
  const { setMap } = getMapContext();

  circleHook();

  useEffect(() => {
    if (!mapRef.current) return;

    // -------> Create the map <-------
    const map = new Map({
      target: mapRef.current,
      layers: [
        new TileLayer({
          source: new OSM()
        })
      ],
      view: new View({
        center: ucDavisCoordinates,
        zoom: 6
      })
    });
    
    setMap(map);

    // Un-Render the map when App is un-rendered
    return () => map.setTarget(undefined);
  }, [setMap]);

  return (
    <div ref={mapRef} style={{width: '90%', height: 600}}></div>
  );
}

export default MapComponent;