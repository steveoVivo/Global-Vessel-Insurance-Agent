import { useEffect, useRef } from 'react';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import getMapContext from './mapContext';
import getRiskContext, { RiskName, NumericRisk } from './riskContext';
import getSelectionContext from './selectionContext';

// Imports that should eventually be moved into a functionality file
import Feature from 'ol/Feature';
import Circle from 'ol/geom/Circle';
import { fromLonLat } from 'ol/proj';
import { Style, Fill, Stroke } from 'ol/style';
import { StyleFunction } from 'ol/style/Style';

import { MapBrowserEvent } from 'ol';
import BaseLayer from 'ol/layer/Base';
import { EventsKey } from 'ol/events';
import { EventTypes } from 'ol/Observable';

interface CountryData {
  "flag": string,
  "country_code": string | null,
  "coordinates": [number, number] | null,
  "vessel_count": number,
  "risk_score": number,
  "event_entropy_norm": number,
  "ship_type_risk_norm": number,
  "open_sea_rate_norm": number,
  "fleet_volatility_norm": number,
}

const CountryNameKey: string = 'countryName';
const CountryCodeKey: string = 'countryCode';
// TODO: Unify the types
const CountryRiskKey: string = 'riskArray';
const CountryFleetKey: string = 'fleetSize';
const CountryIsHovered: string = 'isHovered';
const CountryIsSelected: string = 'isSelected';

// Determines how quickly smaller radii grow compared to larger ones
// Set in a range [0, 1]. Lower values means more varriation. (1/3) is a good standard. 1 is a regular linear size mapping.
const exponential = (1 / 3);

export default function circleHook() {
  const { map } = getMapContext();
  const { riskDistribution } = getRiskContext();
  const { setSelectedCountry } = getSelectionContext();

  // We have to do this to prevent the style function (a closure inside of useEffect) from using stale values
  const riskDistributionClosure = useRef<NumericRisk>(riskDistribution);
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
    let eventKeys: EventsKey[] = [];

    // TODO: Replace this with an animation
    const circleStyleGenerator = (circle: Feature) => {
      // TODO: Some sort of error if these two aren't of the same length?
      const riskArray: NumericRisk = circle.get(CountryRiskKey);
      const riskDistribution: NumericRisk = riskDistributionClosure.current;

      let totalRiskNumerator = 0;
      for (let i = 0; i < riskArray.length; i++) {
        totalRiskNumerator += riskArray[i] * riskDistribution[i];
      }
      const totalRiskDenominator = riskDistribution.reduce((acc, cur) => acc + cur, 0);
      const totalRisk = totalRiskNumerator / totalRiskDenominator;

      const [stroke, fill] = getColorFromRiskScore(totalRisk);

      const defaultStyle = new Style({
        fill: new Fill({ color: fill }),
        stroke: new Stroke({ color: stroke, width: 3 }),
        zIndex: 1
      });

      return (circle.get(CountryIsHovered))
        ? brightenStyle(defaultStyle)
        : (circle.get(CountryIsSelected))
          ? darkenStyle(defaultStyle)
          : defaultStyle;
    }

    const fetchRiskData = async () => {
      try {
        const riskData: CountryData[] = await fetch('/api/data')
          .then(data => data.json())
          .then(data => data.data);

        // TODO: Remove this
        getCircleDataAnalytics(riskData);

        if (!isMounted) return;

        // Measured in meters
        const radiusMin: number = 75000;
        const radiusMax: number = 700000;

        // Normalize fleet sizes to [0, 1] for radius scaling
        const mappableData = riskData.filter(
          (country: CountryData) => country.country_code !== null && country.coordinates !== null
        );

        const fleetSizes = mappableData.map((country: CountryData) => country.vessel_count);

        const exponentiatedData = fleetSizes.map(size => (size ** exponential));
        const smallestFleetExp = Math.min(...exponentiatedData)
        const largestFleetExp = Math.max(...exponentiatedData)

        const fleetNormalizerExp = (size: number): number => (size ** exponential);
        const fleetToRadiusExp = (size: number): number => (radiusMin + (((size - smallestFleetExp) / (largestFleetExp - smallestFleetExp)) * (radiusMax - radiusMin)) );

        const circleFeatures = mappableData.map((countryData: CountryData) => {
          const normalizedFleetSize = fleetNormalizerExp(countryData.vessel_count);
          const diameter = fleetToRadiusExp(normalizedFleetSize);

          // coordinates from backend: [lat, lon] → OpenLayers expects [lon, lat]
          const [lat, lon] = countryData.coordinates!;
          const circleGeom = new Circle(fromLonLat([lon, lat]), diameter);

          const circleFeat = new Feature({ geometry: circleGeom });

          circleFeat.set(CountryNameKey, countryData.flag);
          circleFeat.set(CountryCodeKey, countryData.country_code);
          circleFeat.set(CountryRiskKey, [
            countryData.event_entropy_norm,
            countryData.ship_type_risk_norm,
            countryData.open_sea_rate_norm,
            countryData.fleet_volatility_norm,
          ]);
          circleFeat.set(CountryFleetKey, countryData.vessel_count);

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


        // Use to clear old events out when map or data changes
        eventKeys = [];

        // ==============================
        //        CIRCLE HOVER
        // ==============================
        // TODO: Consider just grabbing this at the top of the function (features.find(countryIsHovered))
        let currentHoveredCircle: Feature<Circle> = null;
        const hoverCircleEvent = (event: MapBrowserEvent) => {
          // Find the circle currently hovered with the smallest radius, if any
          let nextHoveredCircle: Feature<Circle> = null;
          map.forEachFeatureAtPixel(event.pixel, feature => {
            // TODO: Check that the feature belongs to the circle VectorLayer
            if (nextHoveredCircle == null ||
              ((nextHoveredCircle as Feature<Circle>).getGeometry().getRadius()) > ((feature as Feature<Circle>).getGeometry().getRadius())) {
              nextHoveredCircle = feature as Feature<Circle>;
            }
          });

          // If the circle the cursor is pointing to is already selected, do not select the "next best", just return
          if (nextHoveredCircle == currentSelectedCircle) {
            // In this case, we need to ensure the previously hovered circle is not still hovered
            if (currentHoveredCircle) {
              currentHoveredCircle.set(CountryIsHovered, false);
              currentHoveredCircle = null;
            }
            return;
          }

          // The `StyleFunction` will check the `CountryIsHovered` property and update on it's own
          // Therefore, we only need to consider cases when the style of 1+ circle(s) needs to change
          if (nextHoveredCircle) {
            // CASE 1: User went from hovering over nothing, to a new circle
            if (!currentHoveredCircle) {
              nextHoveredCircle.set(CountryIsHovered, true);
              currentHoveredCircle = nextHoveredCircle;
            // CASE 2: User went from hovering over one circle, to a different one
            } else if (currentHoveredCircle != nextHoveredCircle) {
              nextHoveredCircle.set(CountryIsHovered, true);
              currentHoveredCircle.set(CountryIsHovered, false);
              currentHoveredCircle = nextHoveredCircle;
            }
          } else {
            // CASE 3: User went from hovering over a circle, to nothing
            if (currentHoveredCircle) {
              currentHoveredCircle.set(CountryIsHovered, false);
              currentHoveredCircle = null;
            }
          }
        }
        const hoverEventKey = map.on('pointermove', hoverCircleEvent);
        eventKeys.push(hoverEventKey);

        // ==============================
        //        CIRCLE CLICK
        // ==============================
        let currentSelectedCircle: Feature<Circle> = null;
        const selectCircleEvent = (event: MapBrowserEvent) => {
          // Find the circle currently selected with the smallest radius, if any
          let nextSelectedCircle: Feature<Circle> = null;
          map.forEachFeatureAtPixel(event.pixel, feature => {
            // TODO: Check that the feature belongs to the circle VectorLayer
            if (nextSelectedCircle == null ||
              ((nextSelectedCircle as Feature<Circle>).getGeometry().getRadius()) > ((feature as Feature<Circle>).getGeometry().getRadius())) {
              nextSelectedCircle = feature as Feature<Circle>;
            }
          });

          // The `StyleFunction` will check the `CountryIsSelected` property and update on it's own
          // Therefore, we only need to consider cases when the style of 1+ circle(s) needs to change
          if (nextSelectedCircle) {
            // CASE 1: User went from selecting nothing, to selecting a feature
            if (!currentSelectedCircle) {
              // TODO: If you get bugs, you might need to check if this is hovered and set hovered to null here
              nextSelectedCircle.set(CountryIsHovered, false); // TODO: Try and toggle this off and see what happens
              nextSelectedCircle.set(CountryIsSelected, true);
              currentSelectedCircle = nextSelectedCircle;
            // CASE 2: User went from selecting one feature, to another
            } else if (nextSelectedCircle != currentSelectedCircle) {
              nextSelectedCircle.set(CountryIsHovered, false);
              nextSelectedCircle.set(CountryIsSelected, true);
              currentSelectedCircle.set(CountryIsSelected, false);
              currentSelectedCircle = nextSelectedCircle;
            }
          } else {
            // CASE 3: User unselected a circle
            if (currentSelectedCircle) {
              currentSelectedCircle.set(CountryIsSelected, false);
              currentSelectedCircle = null;
            }
          }
          
          if (currentSelectedCircle) {
            setSelectedCountry({
              country: currentSelectedCircle.get(CountryNameKey),
              countryCode: currentSelectedCircle.get(CountryCodeKey),
              risk: currentSelectedCircle.get(CountryRiskKey),
              fleetSize: currentSelectedCircle.get(CountryFleetKey)
            });
          } else {
            setSelectedCountry(null);
          }
        }
        const clickEventKey = map.on('click', selectCircleEvent);
        eventKeys.push(clickEventKey);

      } catch (_) {
        // TODO: Make this real
        console.error('Caught an error ;^)')
      }
    }

    fetchRiskData();

    return () => {
      isMounted = false;

      // Clear the layer off the old map
      if (circleVectorLayer != null) {
        map.removeLayer(circleVectorLayer);
      }

      // Remove cost of listeners for unused map
      eventKeys.forEach((key: EventsKey) => {
        map.un(key.type as EventTypes, key.listener);
      });
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

// The incoming style MUST have an RGBA fill and an RGB stroke
export function brightenStyle(style: Style): Style {
  const valueToBrightenBy = 40;
  const increaseNumberBrightness = ((num: number) => {
    if (num < 1) return num;
    return ((num + valueToBrightenBy) <= 255) ? (num + valueToBrightenBy) : 255;
  });

  const returnStyle = style.clone();

  const fill = style.getFill();
  const fillColor = fill.getColor();
  const fillRGB = fillColor.toString().slice(5, -1);
  const fillArray = fillRGB.split(',').map(Number).map(increaseNumberBrightness)

  const returnFill = returnStyle.getFill();
  returnFill.setColor('rgba(' + fillArray.join(',') + ')');
  returnStyle.setFill(returnFill);


  const stroke = style.getStroke();
  const strokeColor = stroke.getColor();
  const strokeRGB = strokeColor.toString().slice(5, -1);
  const strokeArray = strokeRGB.split(',').map(Number).map(increaseNumberBrightness);

  const returnStroke = returnStyle.getStroke();
  returnStroke.setColor('rgba(' + strokeArray.join(',') + ')');
  returnStyle.setStroke(returnStroke);

  returnStyle.setZIndex(3);

  return returnStyle;
}

// The incoming style MUST have an RGBA fill and an RGB stroke
function darkenStyle(style: Style): Style {
  const valueToDarkenBy = 60;
  const increaseNumberBrightness = ((num: number) => {
    if (num < 1) return num;
    return ((num - valueToDarkenBy) >= 0) ? (num - valueToDarkenBy) : 0;
  });

  const returnStyle = style.clone();

  const fill = style.getFill();
  const fillColor = fill.getColor();
  const fillRGB = fillColor.toString().slice(5, -1);
  const fillArray = fillRGB.split(',').map(Number).map(increaseNumberBrightness)

  const returnFill = returnStyle.getFill();
  returnFill.setColor('rgba(' + fillArray.join(',') + ')');
  returnStyle.setFill(returnFill);


  const stroke = style.getStroke();
  const strokeColor = stroke.getColor();
  const strokeRGB = strokeColor.toString().slice(5, -1);
  const strokeArray = strokeRGB.split(',').map(Number).map(increaseNumberBrightness);

  const returnStroke = returnStyle.getStroke();
  // returnStroke.setColor('rgba(' + strokeArray.join(',') + ')');
  returnStroke.setColor('black');
  returnStyle.setStroke(returnStroke);

  returnStyle.setZIndex(2);

  return returnStyle;
}

// Input should be [0, 1]
// NOTE: This is currently red -> green. Could be any two colors in the future
export function getColorFromRiskScore(riskScore: number): [string, string] {
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

  const events = data.map(country => country.event_entropy_norm);
  const eventsMax = Math.max(...events);
  const eventsMin = Math.min(...events);
  const ships = data.map(country => country.ship_type_risk_norm);
  const shipsMax = Math.max(...ships);
  const shipsMin = Math.min(...ships);
  const openSea = data.map(country => country.open_sea_rate_norm);
  const openSeaMax = Math.max(...openSea);
  const openSeaMin = Math.min(...openSea);
  const fleetVol = data.map(country => country.fleet_volatility_norm);
  const fleetVolMax = Math.max(...fleetVol);
  const fleetVolMin = Math.min(...fleetVol);

  console.log('Count Max: ', vesselCountMax, ', and min: ', vesselCountMin);
  console.log('Event Entropy Risk Max: ', eventsMax, ', and min: ', eventsMin);
  console.log('Ship Type Risk Max: ', shipsMax, ', and min: ', shipsMin);
  console.log('Open Sea Risk Max: ', openSeaMax, ', and min: ', openSeaMin);
  console.log('Fleet Volatility Risk Max: ', fleetVolMax, ', and min: ', fleetVolMin);
}
