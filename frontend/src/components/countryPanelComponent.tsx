import { useMemo } from 'react';

import getSelectionContext from './selectionContext';
import getRiskContext from './riskContext';
import TrendComponent from './trendComponent';
import AccidentListComponent from './accidentListComponent';

import { getColorFromRiskScore } from './circleHook';
import unknownFlagImage from './../assets/unknown.png';

/**
 * Component respondible for displaying country flag, risk score, vessel count, and temporal trend data
 * @desc React - Component
 */
function CountryPanelComponent() {
  const { currentCountry, currentCountryCode, currentRisk, currentFleetSize } = getSelectionContext();
  const { riskDistribution } = getRiskContext();

  const flagSrc: string = useMemo(() => {
    if (!currentCountry || !currentCountryCode) return unknownFlagImage;
    return `https://flagcdn.com/w160/${currentCountryCode.toLowerCase()}.png`;
  }, [currentCountry, currentCountryCode]);

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
    : 'United States 🦅🦅';
  const fleetText = currentFleetSize?.toLocaleString();

  return (
    <div className='country-panel-container'>
      <div className='country-panel-info-row'>
        <img className='country-panel-flag' src={flagSrc} onError={e => e.currentTarget.src = unknownFlagImage} />
        <div className='country-panel-current'>{countryText}</div>
        <div className='country-panel-risk'>
          <div>Risk Score:
            <span style={{ color: getColorFromRiskScore(totalRisk / 100)[1] }}> {totalRisk} / 100</span>
          </div>
          <div>Vessels:
            <span style={{ color: 'darkgray' }}> {fleetText}</span>
          </div>
        </div>
      </div>
      <TrendComponent />
      <AccidentListComponent />
    </div>
  );
}

export default CountryPanelComponent;
