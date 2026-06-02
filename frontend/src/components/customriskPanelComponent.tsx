import { useRef } from 'react';
import getRiskContext, { RiskTypeToEnglishName } from './riskContext';

// TODO: Do I still need this here?
import 'ol/ol.css';

function CustomriskPanelComponent() {
  const { riskDistributionName, setCustomDistribution, setDistribution } = getRiskContext();

  const isCustom = riskDistributionName == 'Custom';
  const riskTypeName = RiskTypeToEnglishName(riskDistributionName);

  const accidentRef = useRef<HTMLInputElement>(null);
  const flagRef = useRef<HTMLInputElement>(null);
  const eventRef = useRef<HTMLInputElement>(null);
  const investigationRef = useRef<HTMLInputElement>(null);
  const trendRef = useRef<HTMLInputElement>(null);

  const changeInputValue = () => {
    setCustomDistribution([
      (Number(accidentRef.current.value) / 100), (Number(flagRef.current.value) / 100),
      (Number(eventRef.current.value) / 100), (Number(investigationRef.current.value) / 100),
      (Number(trendRef.current.value) / 100)]);
  }

  return (
    <div className='custom-risk-panel'>
      <div> Current Risk Factor: {riskTypeName} </div>
      <div className='custom-risk-input-container'>
        <div className='risk-input-container'>
          <div> Accident Rate </div>
          <div>
            <input onChange={changeInputValue} ref={accidentRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Flag Safety </div>
          <div>
            <input onChange={changeInputValue} ref={flagRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Event Entropy </div>
          <div>
            <input onChange={changeInputValue} ref={eventRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Investigation </div>
          <div>
            <input onChange={changeInputValue} ref={investigationRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Trend Slope </div>
          <div>
            <input onChange={changeInputValue} ref={trendRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
      </div>
      <div className='custom-factor-warning' style={{ display: !isCustom ? 'flex' : 'none' }}>
        <div style={{ color: 'darkslategray' }}> [Inputs only effect map when risk factor is set to custom. </div>
        <div className='custom-factor-button' onClick={() => setDistribution('Custom')}> Click here </div>
        <div style={{ color: 'darkslategray' }}> to change it] </div>
      </div>
    </div>
  );
}

export default CustomriskPanelComponent;