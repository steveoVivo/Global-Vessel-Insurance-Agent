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

import centroids from './../data/countries';
import { MapBrowserEvent } from 'ol';
import BaseLayer from 'ol/layer/Base';
import { EventsKey } from 'ol/events';
import { EventTypes } from 'ol/Observable';

interface CountryData {
  "flag": string,
  "vessel_count": number,
  "risk_score": number,
  "accident_rate_norm": number,
  "flag_safety_risk_norm": number,
  "event_entropy_norm": number,
  "investigation_rate_norm": number,
  "trend_slope_norm": number
}

const CountryNameKey: string = 'countryName';
// TODO: Unify the types
const CountryRiskKey: string = 'riskArray';
const CountryFleetKey: string = 'fleetSize';
const CountryIsHovered: string = 'isHovered';
const CountryIsSelected: string = 'isSelected';

export default function circleHook() {
  const { map } = getMapContext();
  const { riskDistribution } = getRiskContext();
  const { setSelectedCountry } = getSelectionContext();

  // We have to do this to prevent the style function (a closure inside of useEffect) from using stale values
  const riskDistributionClosure = useRef<[number, number, number, number, number]>(riskDistribution);
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
          countryData.event_entropy_norm, countryData.investigation_rate_norm, countryData.trend_slope_norm]);
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

  const accidents = data.map(country => country.accident_rate_norm);
  const accidentsMax = Math.max(...accidents);
  const accidentsMin = Math.min(...accidents);
  const flags = data.map(country => country.flag_safety_risk_norm);
  const flagsMax = Math.max(...flags);
  const flagsMin = Math.min(...flags);
  // const severities = data.map(country => country.severity_risk_norm);
  // const severitiesMax = Math.max(...severities);
  // const severitiesMin = Math.min(...severities);
  // const ships = data.map(country => country.ship_type_risk_norm);
  // const shipsMax = Math.max(...ships);
  // const shipsMin = Math.min(...ships);

  console.log('Count Max: ', vesselCountMax, ', and min: ', vesselCountMin);

  // console.log('ALL Risk Max: ', riskScoreMax, ', and min: ', riskScoreMin);
  console.log('Accident Risk Max: ', accidentsMax, ', and min: ', accidentsMin);
  console.log('Flags Risk Max: ', flagsMax, ', and min: ', flagsMin);
  // console.log('Severities Risk Max: ', severitiesMax, ', and min: ', severitiesMin);
  // console.log('Ships Risk Max: ', shipsMax, ', and min: ', shipsMin);
}