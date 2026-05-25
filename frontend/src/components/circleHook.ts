// useVectorLayer.js
import { useEffect, useRef } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import getMapContext from './mapContext';
import getRiskContext, { RiskName, NumericRisk } from './riskContext';

// Imports that should eventually be moved into a functionality file
import Feature from 'ol/Feature';
import Circle from 'ol/geom/Circle';
import { fromLonLat } from 'ol/proj';
import { Style, Fill, Stroke } from 'ol/style';

import centroids from './../data/countries';
import { MapBrowserEvent } from 'ol';
import BaseLayer from 'ol/layer/Base';

interface CountryData {
  "flag": string,
  "vessel_count": number,
  "risk_score": number,
  "accident_rate_norm": number, 
  "severity_risk_norm": number,
  "ship_type_risk_norm": number,
  "flag_safety_risk_norm": number
}

const CountryNameKey: string = 'countryName';
// TODO: Unify the types
const CountryRiskKey: string = 'riskArray';

export default function circleHook () {
  const { map } = getMapContext();
  const { riskDistribution } = getRiskContext();

  // We have to do this to prevent the style function (a closure inside of useEffect) from using stale values
  const riskDistributionClosure = useRef<[number, number, number, number]>(riskDistribution);
  useEffect(() => {
    riskDistributionClosure.current = riskDistribution;
  }, [riskDistribution]);

  useEffect(() => {
    if (!map) return;

    // TODO: Reference where you found it
    // Had to look this one up online, best practice for working with async data
    // Prevent the attempt to attach data to the map in the case the map gets unmounted while fetching
    let isMounted: boolean = true;
    let circleVectorLayer: VectorLayer = null;

    // TODO: Replace this with an animation
    const circleStyleGenerator = (circle: Feature) => {
      // TODO: Some sort of error if these two aren't of the same length?
      const riskArray: NumericRisk = circle.get(CountryRiskKey);
      const riskDistribution: NumericRisk = riskDistributionClosure.current;

      let totalRiskValue = 0;
      for(let i = 0; i < riskArray.length; i++) {
        totalRiskValue += riskArray[i] * riskDistribution[i];
      }

      const [stroke, fill] = getColorFromRiskScore(totalRiskValue);

      return new Style({
        fill: new Fill({ color: fill }),
        stroke: new Stroke({ color: stroke, width: 3 })
      });
    }

    const fetchRiskData = async () => {
      try {
        const riskData: CountryData[] = await fetch('/api/data')
          .then(data => data.json())
          .then(data => data.data);

        // TODO: Remove this
        // getCircleDataAnalytics(riskData);

        if (!isMounted) return;

        // Mesaured in meters
        const radiusMin: number = 75000;
        const radiusMax: number = 700000;

        // This code effectively normalizes country count - pushing all values to a scale between [0, 1]
        const fleetSizes = riskData.map((country: CountryData) => country.vessel_count);
        const smallestFleet = Math.min(...fleetSizes);
        const largestFleet = Math.max(...fleetSizes);
        const fleetNormaizer = (size: number): number => ((size - smallestFleet) / (largestFleet - smallestFleet)); 

        const countryCodes = Object.keys(centroids);
        const backendMatchingCountryCodes = countryCodes.filter((code: string) => {
          const countryName = centroids[code].name;
          return riskData.find(country => country.flag == countryName);
        });

        const circleFeatures = backendMatchingCountryCodes.map((countryCode: string) => {
          // Not great, you do the same thing that you do in the filter function. You can mesh this into that
          const countryName = centroids[countryCode].name;
          const countryData = riskData.find(country => country.flag == countryName);

          // Create radius (from fleet count)
          // NOTE: This is a basic LERP function, similar to Math.LERP from C# (used a lot in gamedev)
          const normalizedFleetSize = fleetNormaizer(countryData.vessel_count);
          const radius = radiusMin + ((radiusMax - radiusMin) * normalizedFleetSize);

          // Get Coordinates
          const coordinate = centroids[countryCode].coordinates;
          const coordinateFlip = [coordinate[1], coordinate[0]];
          // Create Geometry
          const circleGeom = new Circle(
            fromLonLat(coordinateFlip),
            radius * 2  // TODO: Remove this multiplication factor once Yoshiki fixes the output risk range
          )
          // Create Feature
          const circleFeat = new Feature({
            geometry: circleGeom
          });

          // Set properties in the feature to be pulled later when rendering circles
          circleFeat.set(CountryNameKey, centroids[countryCode].name);
          circleFeat.set(CountryRiskKey, [countryData.accident_rate_norm, countryData.flag_safety_risk_norm,
            countryData.severity_risk_norm, countryData.ship_type_risk_norm]);

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
        console.error('Caught an error ;^)')
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

// Input should be [0, 1]
// NOTE: This is currently red -> green. Could be any two colors in the future
function getColorFromRiskScore(riskScore: number): [string, string] {
  const red: number = Math.floor(255 * riskScore);
  const green: number = Math.floor(128 * (1 - riskScore));
  // RGB of "red": rgb(255, 0, 0)
  // RGB or "green": rgb(0, 128, 0)
  return [`rgba(${red}, ${green}, 0)`, `rgba(${red}, ${green}, 0, 0.65)`]
}

function getCircleDataAnalytics(data: CountryData[]): void {
  // .sort() will sort an array in place, put the vessels with the highest count first
  const riskiestCountries = [...data].sort((a, b) => a.risk_score - b.risk_score);
  const biggestCountries = [...data].sort((a, b) => a.vessel_count - b.vessel_count);

  console.log(riskiestCountries);
  console.log(biggestCountries);

  // const riskScore = data.map(country => country.risk_score);
  // const riskScoreMax = Math.max(...riskScore);
  // const riskScoreMin = Math.min(...riskScore);
  const vesselCount = data.map(country => country.vessel_count);
  const vesselCountMax = Math.max(...vesselCount);
  const vesselCountMin = Math.min(...vesselCount);

  const accidents = data.map(country => country.accident_rate_norm);
  const accidentsMax = Math.max(...accidents);
  const accidentsMin = Math.min(...accidents);
  const flags = data.map(country => country.flag_safety_risk_norm);
  const flagsMax = Math.max(...flags);
  const flagsMin = Math.min(...flags);
  const severities = data.map(country => country.severity_risk_norm);
  const severitiesMax = Math.max(...severities);
  const severitiesMin = Math.min(...severities);
  const ships = data.map(country => country.ship_type_risk_norm);
  const shipsMax = Math.max(...ships);
  const shipsMin = Math.min(...ships);

  console.log('Count Max: ', vesselCountMax, ', and min: ', vesselCountMin);

  // console.log('ALL Risk Max: ', riskScoreMax, ', and min: ', riskScoreMin);
  console.log('Accident Risk Max: ', accidentsMax, ', and min: ', accidentsMin);
  console.log('Flags Risk Max: ', flagsMax, ', and min: ', flagsMin);
  console.log('Severities Risk Max: ', severitiesMax, ', and min: ', severitiesMin);
  console.log('Ships Risk Max: ', shipsMax, ', and min: ', shipsMin);
}