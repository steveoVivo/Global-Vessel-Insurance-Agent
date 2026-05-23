// useVectorLayer.js
import { useEffect } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import getMapContext from './mapContext';

// Imports that should eventually be moved into a functionality file
import Feature from 'ol/Feature';
import Circle from 'ol/geom/Circle';
import { fromLonLat } from 'ol/proj';
import { Style, Fill, Stroke } from 'ol/style';

export default function circleHook () {
  const { map } = getMapContext();

  useEffect(() => {
    if (!map) return;

    // SF, Oakland, and Twin Peaks. I got the exact co-ordinates from Google Gemini
    const testCoordinates: number[][] = [
      [-122.4194, 37.7749],
      [-122.2711, 37.8044],
      [-122.4467, 37.7337]
    ];
    // Mesaured in meters
    const radius: number = 5000;

    // TODO: Is this the best way of doing this? Not a huge fan of literally drawing images
    const circleGeometeries = testCoordinates.map(coordinate => {
      return new Circle(
        fromLonLat(coordinate),
        radius
      )
    });
    const circleFeatures = circleGeometeries.map(geometry => {
      return new Feature(geometry);
    });

    const circleStyle = new Style({
      fill: new Fill({ color: 'rgba(160, 0, 0, 0.65)' }),
      stroke: new Stroke({ color: 'rgb(160, 0, 0)', width: 3 })
    });
    circleFeatures.forEach(feature => feature.setStyle(circleStyle));

    const circleSource = new VectorSource({
      features: circleFeatures,
    });
    const circleLayer = new VectorLayer({
      source: circleSource
    });
    
    map.addLayer(circleLayer);

    // Clean up layer when data changes or component unmounts
    return () => {
      map.removeLayer(circleLayer);
    };
  }, [map]);
};