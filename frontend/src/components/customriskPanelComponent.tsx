import { useRef, useState } from 'react';
import getRiskContext, { riskTypeToEnglishName } from './riskContext';
import { NumericRisk } from './riskContext';

// TODO: Do I still need this here?
import 'ol/ol.css';

function CustomriskPanelComponent() {
  const { riskDistribution, riskDistributionName, setCustomDistribution, setDistribution } = getRiskContext();

  const eventRef = useRef<HTMLInputElement>(null);
  const investigationRef = useRef<HTMLInputElement>(null);
  const flagRef = useRef<HTMLInputElement>(null);
  const shipTypeRef = useRef<HTMLInputElement>(null);
  const openSeaRef = useRef<HTMLInputElement>(null);
  const solasRef = useRef<HTMLInputElement>(null);
  const indexedRefs = [eventRef, investigationRef, flagRef, shipTypeRef, openSeaRef, solasRef];

  const isCustom = riskDistributionName == 'Custom';
  const riskTypeName = riskTypeToEnglishName(riskDistributionName);

  const totalRiskSum = Math.floor(100 * riskDistribution.reduce((cur, acc) => cur + acc));
  const isRiskSum100 = totalRiskSum == 100;

  const changeInputValue = () => {
    // Data cleaning - remove trailing 0s, ensure values cannot drop below 0 or above 1000
    indexedRefs.forEach(ref => {
      ref.current.value = '' + (Number(ref.current.value));
      if (Number(ref.current.value) < 0) ref.current.value = '0';
      if (Number(ref.current.value) > 1000) ref.current.value = '1000';
    });

    setCustomDistribution([
      (Number(eventRef.current.value) / 100), (Number(investigationRef.current.value) / 100),
      (Number(flagRef.current.value) / 100), (Number(shipTypeRef.current.value) / 100),
      (Number(openSeaRef.current.value) / 100), (Number(solasRef.current.value) / 100)]);
  }

  return (
    <div className='custom-risk-panel'>
      {/* TODO: Move this outside. The display one can be replaced by classname hidden */}
      <div style={{display: 'flex', flexDirection:'row', justifyContent: 'center', gap: '5%'}}>
        <div> Current Risk Factor: <span style={{color: 'darkgray'}}>{riskTypeName}</span> </div>
        <div className={isRiskSum100 ? 'hidden' : ''}>
          Sum of weights: <span style={{color: 'darkgray'}}>{totalRiskSum}</span>%
        </div>
      </div>
      <div className='custom-risk-input-container'>
        <div className='risk-input-container'>
          <div> Event Entropy </div>
          <div>
            <input onInput={changeInputValue}
              ref={eventRef} type="number" min="0" max="100" step="1" defaultValue="17" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Investigation </div>
          <div>
            <input onInput={changeInputValue}
              ref={investigationRef} type="number" min="0" max="100" step="1" defaultValue="17" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Flag Safety </div>
          <div>
            <input onInput={changeInputValue}
              ref={flagRef} type="number" min="0" max="100" step="1" defaultValue="17" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Ship Type </div>
          <div>
            <input onInput={changeInputValue}
              ref={shipTypeRef} type="number" min="0" max="100" step="1" defaultValue="17" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Open Sea </div>
          <div>
            <input onInput={changeInputValue}
              ref={openSeaRef} type="number" min="0" max="100" step="1" defaultValue="16" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> SOLAS Non-compliance </div>
          <div>
            <input onInput={changeInputValue}
              ref={solasRef} type="number" min="0" max="100" step="1" defaultValue="16" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
      </div>
      <div className='custom-factor-warning' style={{ display: isRiskSum100 ? 'none' : 'flex' }}>
        <div style={{ color: 'darkslategray' }}> When weighted sum exceeds 100, weights are normalized. Output is still valid. </div>
      </div>
      <div className='custom-factor-warning' style={{ display: isCustom ? 'none' : 'flex' }}>
        <div style={{ color: 'darkslategray' }}> [Inputs only effect map when risk factor is set to custom. </div>
        <div className='custom-factor-button' onClick={() => setDistribution('Custom')}> Click here </div>
        <div style={{ color: 'darkslategray' }}> to change it] </div>
      </div>
    </div>
  );
}

export default CustomriskPanelComponent;
