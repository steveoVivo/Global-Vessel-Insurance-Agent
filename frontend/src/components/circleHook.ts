// useVectorLayer.js
import { useEffect } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import getMapContext from './mapContext';
import getRiskContext from './riskContext';

// Imports that should eventually be moved into a functionality file
import Feature from 'ol/Feature';
import Circle from 'ol/geom/Circle';
import { fromLonLat } from 'ol/proj';
import { Style, Fill, Stroke } from 'ol/style';

import centroids from './../data/countries';
import { MapBrowserEvent } from 'ol';
import BaseLayer from 'ol/layer/Base';

interface CountryData {
  country: string,
  risk_score: number,
  vessel_count: number,
  risk_score_A?: number,
  risk_score_B?: number,
  risk_score_C?: number,
  risk_score_D?: number
}
const CountryNameKey: string = 'countryName';

export default function circleHook () {
  const { map } = getMapContext();
  const { riskDistribution, setDistribution, setCustomDistribution } = getRiskContext();

  // TODO: Delete this. I just did it to avoid the error
  console.log(riskDistribution);

  useEffect(() => {
    if (!map) return;

    // TODO: Reference where you found it
    // Had to look this one up online, best practice for working with async data
    // Prevent the attempt to attach data to the map in the case the map gets unmounted while fetching
    let isMounted: boolean = true;
    let circleVectorLayer: VectorLayer = null;

    // TODO: Replace this with an animation
    const circleStyleGenerator = (circle: Feature) => {
      const testColorArray = [
        'red', 'purple', 'blue', 'orange', 'green'
      ]
      const indexOfOne = riskDistribution.indexOf(1);
      const color = testColorArray[indexOfOne];

      return new Style({
        fill: new Fill({ color: 'rgba(160, 0, 0, 0.65)' }),
        stroke: new Stroke({ color, width: 3 })
      });
    }

    const fetchRiskData = async () => {
      try {
        const riskData: CountryData[] = await fetch('/api/data')
          .then(data => data.json())
          .then(data => data.data);

        if (!isMounted) return;

        // Mesaured in meters
        const radiusMin: number = 75000;
        const radiusMax: number = 350000;

        const countryCodes = Object.keys(centroids);
        const backendMatchingCountryCodes = countryCodes.filter((code: string) => {
          const countryName = centroids[code].name;
          return riskData.find(country => country.country == countryName);
        });

        const circleFeatures = backendMatchingCountryCodes.map((countryCode: string) => {
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

        circleFeatures.forEach((circle: Feature) => circle.setStyle(circleStyleGenerator))

        const circleSourceLayer = new VectorSource({
          features: circleFeatures
        });

        circleVectorLayer = new VectorLayer({
          source: circleSourceLayer
        });

        map.addLayer(circleVectorLayer);

      } catch (_) {
        // TODO: Make this real
        console.log('Caught an error ;^)')
      }
    }

    fetchRiskData();

    // NOTE: This will give information about the data being sent
    // getCircleDataAnalytics(data);

    // TODO: This

    // const clickCircleEvent = (event: MapBrowserEvent) => {
    //   const countryName = map.forEachFeatureAtPixel(event.pixel, (feature: Feature) => {
    //     return feature.get(CountryNameKey);
    //   });

    //   if (countryName) {
    //     console.log(countryName);
    //   }
    // };

    // map.on('click', clickCircleEvent)

    // Clean up layer when data changes or component unmounts
    return () => {
      isMounted = false;
      // TODO: You 100% need to come back to these two

      // map.removeLayer(circleLayer);
      // TODO: Do I need this? Pretty sure I do
      // map.un('click', clickCircleEvent);
    };
    
  }, [map]);

  // This hook forces the style function to update when riskDistribution updates
  useEffect(() => {
    if (!map) return;

    map.getLayers().forEach((layer: BaseLayer) => {
      // TODO: Develop a unique layerID
      if (layer instanceof VectorLayer) {
        layer.changed();
      }
    });
  }, [map, riskDistribution]);
};

function getCircleDataAnalytics(data: CountryData[]): void {
  // .sort() will sort an array in place, put the vessels with the highest count first
  const riskiestCountries = [...data].sort((a, b) => a.risk_score - b.risk_score);
  const biggestCountries = [...data].sort((a, b) => a.vessel_count - b.vessel_count);

  console.log(riskiestCountries);
  console.log(biggestCountries);

  const riskScore = data.map(country => country['risk_score']);
  const riskScoreMax = Math.max(...riskScore);
  const riskScoreMin = Math.min(...riskScore);
  const vesselCount = data.map(country => country['vessel_count']);
  const vesselCountMax = Math.max(...vesselCount);
  const vesselCountMin = Math.min(...vesselCount);
  console.log('Risk Max: ', riskScoreMax, ', and min: ', riskScoreMin);
  console.log('Count Max: ', vesselCountMax, ', and min: ', vesselCountMin);
}