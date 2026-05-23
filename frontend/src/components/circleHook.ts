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

import centroids from './../data/countries';
import { MapBrowserEvent } from 'ol';

const CountryNameKey: string = 'countryName';

export default function circleHook () {
  const { map } = getMapContext();

  useEffect(() => {
    if (!map) return;

    // Mesaured in meters
    const radius: number = 500000;
    const radiusMin: number = 75000;
    const radiusMax: number = 350000;

    const countryCodes = Object.keys(centroids);
    const circleFeatures = countryCodes.map((countryCode: string) => {
      // Create radius (random)
      const randomRadius = Math.floor(Math.random() * (radiusMax - radiusMin + 1)) + radiusMin;

      // Get Coordinates
      const coordinate = centroids[countryCode].coordinates;
      const coordinateFlip = [coordinate[1], coordinate[0]];
      // Create Geometry
      const circleGeom = new Circle(
        fromLonLat(coordinateFlip),
        randomRadius
      )
      // Create Feature
      const circleFeat = new Feature({
        geometry: circleGeom
      });
      circleFeat.set(CountryNameKey, centroids[countryCode].name);

      return circleFeat;
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

    const clickCircleEvent = (event: MapBrowserEvent) => {
      const countryName = map.forEachFeatureAtPixel(event.pixel, (feature: Feature) => {
        return feature.get(CountryNameKey);
      });

      if (countryName) {
        console.log(countryName);
      }
    };

    map.on('click', clickCircleEvent)

    // Clean up layer when data changes or component unmounts
    return () => {
      map.removeLayer(circleLayer);
      // TODO: Do I need this? Pretty sure I do
      map.un('click', clickCircleEvent);
    };
  }, [map]);
};