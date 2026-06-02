// TODO: Do I still need this here?
import 'ol/ol.css';

import { useRef } from 'react';

import getSelectionContext from './selectionContext';
import getRiskContext from './riskContext';

import { getColorFromRiskScore } from './circleHook';

// TODO: Of course, move centroids to the BE
import centroids from './../data/countries';


function CountryPanelComponent() {
  const { currentCountry, currentRisk } = getSelectionContext();
  const { riskDistribution } = getRiskContext();

  const flagRef = useRef<HTMLImageElement>(null);

  // TODO: idr if this is the right way of doing this, consider a useEffect?
  if (flagRef.current && currentCountry) {
    const countryCodesUppercase = Object.keys(centroids);
    const matchingCodeUppercase = countryCodesUppercase.find((code: string) => {
      const currentCentroid = centroids[code];
      return currentCentroid.name == currentCountry
    });

    // TODO: We should add a default SRC on timeout
    if (matchingCodeUppercase) {
      const matchingCodeLowercase = matchingCodeUppercase.toLowerCase();
      flagRef.current.src = `https://flagcdn.com/w160/${matchingCodeLowercase}.png`;
    }
  }

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

  const countryText = currentCountry != 'United States'
    ? currentCountry
    : '~!~ OLD GLORY ~!~ 🦅🦅🇺🇸'

  return (
    <div>
      <img ref={flagRef}/>
      <span style={{ display: (currentCountry == null) ? 'none' : 'inline' }}> Currently Selected Country: {countryText} </span>
      <span style={{ display: (currentCountry == null) ? 'none' : 'inline' }}> // </span>
      <span style={{ display: (currentCountry == null) ? 'none' : 'inline', 
        color: getColorFromRiskScore(totalRisk / 100)[1] }}
        className='total-risk-display'> {totalRisk} </span>
      <span style={{ display: (currentCountry != null) ? 'none' : 'inline', color: 'darkslategray' }}> [No country currently selected] </span>
    </div>
  );
}

export default CountryPanelComponent;