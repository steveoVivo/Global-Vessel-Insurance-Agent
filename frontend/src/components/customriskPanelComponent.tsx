import { useRef } from 'react';
import getRiskContext, { RiskTypeToEnglishName } from './riskContext';

// TODO: Do I still need this here?
import 'ol/ol.css';

function CustomriskPanelComponent() {
  const { riskDistributionName, setCustomDistribution, setDistribution } = getRiskContext();

  const isDisabled = riskDistributionName != 'Custom';
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
      <div style={{ display: isDisabled ? 'flex' : 'none', flexDirection: 'column' }}>
        <div> Current Risk Factor </div>
        <div> is {riskTypeName} </div>
        <button onClick={() => setDistribution('Custom')}> Enable Custom Risk </button>
      </div>
      <div className='risk-input-container'>
        <div> Accident Rate </div>
        <div>
          <input onChange={changeInputValue} ref={accidentRef} type="number" min="0" max="100" defaultValue="20" disabled={isDisabled} />
          <span className="risk-input-percentage">%</span>
        </div>
      </div>
      <div className='risk-input-container'>
        <div> Flag Safety </div>
        <div>
          <input onChange={changeInputValue} ref={flagRef} type="number" min="0" max="100" defaultValue="20" disabled={isDisabled} />
          <span className="risk-input-percentage">%</span>
        </div>
      </div>
      <div className='risk-input-container'>
        <div> Event Entropy </div>
        <div>
          <input onChange={changeInputValue} ref={eventRef} type="number" min="0" max="100" defaultValue="20" disabled={isDisabled} />
          <span className="risk-input-percentage">%</span>
        </div>
      </div>
      <div className='risk-input-container'>
        <div> Investigation </div>
        <div>
          <input onChange={changeInputValue} ref={investigationRef} type="number" min="0" max="100" defaultValue="20" disabled={isDisabled} />
          <span className="risk-input-percentage">%</span>
        </div>
      </div>
      <div className='risk-input-container'>
        <div> Trend Slope </div>
        <div>
          <input onChange={changeInputValue} ref={trendRef} type="number" min="0" max="100" defaultValue="20" disabled={isDisabled} />
          <span className="risk-input-percentage">%</span>
        </div>
      </div>
    </div>
  );
}

export default CustomriskPanelComponent;