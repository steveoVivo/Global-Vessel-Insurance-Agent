// TODO: Do I still need this here?
import 'ol/ol.css';

import { useMemo } from 'react';

import getSelectionContext from './selectionContext';
import getRiskContext from './riskContext';

import { getColorFromRiskScore } from './circleHook';

// TODO: Of course, move centroids to the BE
import centroids from './../data/countries';

import unknownFlagImage from './../assets/unknown.png';


function CountryPanelComponent() {
  const { currentCountry, currentRisk, currentFleetSize } = getSelectionContext();
  const { riskDistribution } = getRiskContext();

  // Compute the image source of the flag
  const flagSrc: string = useMemo(() => {
    // Done for safety, but could return anything. On paper, this will never render
    if (!currentCountry) return unknownFlagImage;

    // Use the centroid file to find the country code needed to query flagCDN for this flag
    const countryCodesUppercase = Object.keys(centroids);
    const matchingCodeUppercase = countryCodesUppercase.find((code: string) => {
      const currentCentroid = centroids[code];
      return currentCentroid.name == currentCountry
    });

    // If this flag doesn't have a matching country code, use default "unknown" flag
    if (!matchingCodeUppercase) return unknownFlagImage;

    const matchingCodeLowercase = matchingCodeUppercase.toLowerCase();
    return `https://flagcdn.com/w160/${matchingCodeLowercase}.png`;
  }, [currentCountry]);
  


  // TODO: This is just copied from the calulation function in circleHook. Move them both into one function
  let totalRisk: number;
  if (currentRisk) {
    let totalRiskNumerator = 0;
    for (let i = 0; i < currentRisk.length; i++) {
      totalRiskNumerator += currentRisk[i] * riskDistribution[i];
    }

    const totalRiskDenominator = riskDistribution.reduce((acc, cur) => acc + cur, 0);
    totalRisk = totalRiskNumerator / totalRiskDenominator;
    totalRisk *= 100;
    totalRisk = Math.floor(totalRisk);
  }


  // Simple custom string mutations for various input data
  const countryText = currentCountry != 'United States'
    ? currentCountry
    : 'United States 🦅🦅';
  const fleetText = currentFleetSize?.toLocaleString();

  return (
    (!currentCountry)
      ? (
        <div style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignContent: 'center', flexWrap: 'wrap'}}>
        <div style={{ color: 'darkslategray'}}> [Select a country on the map to interact with this panel] </div>
        </div>
        )
      : (
        <div className='country-panel-container'>
          <img className='country-panel-flag' src={flagSrc} onError={e => e.currentTarget.src=unknownFlagImage}/>
          <div className='country-panel-current'> {countryText} </div>
          <div className='country-panel-risk'>
              <div> Risk Score: 
                <span style={{ color: getColorFromRiskScore(totalRisk / 100)[1] }}> {totalRisk} / 100 </span>
              </div>
              <div> Vessel Count: 
                <span style={{ color: 'darkgray'}}> {fleetText} </span>
              </div>
          </div>
        </div>
      ));
}

export default CountryPanelComponent;