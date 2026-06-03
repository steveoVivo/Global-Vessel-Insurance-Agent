import { useRef, useState } from 'react';
import getRiskContext, { riskTypeToEnglishName } from './riskContext';
import { NumericRisk } from './riskContext';

// TODO: Do I still need this here?
import 'ol/ol.css';

function CustomriskPanelComponent() {
  const { riskDistribution, riskDistributionName, setCustomDistribution, setDistribution } = getRiskContext();

  const isCustom = riskDistributionName == 'Custom';
  const riskTypeName = riskTypeToEnglishName(riskDistributionName);

  const accidentRef = useRef<HTMLInputElement>(null);
  const flagRef = useRef<HTMLInputElement>(null);
  const eventRef = useRef<HTMLInputElement>(null);
  const investigationRef = useRef<HTMLInputElement>(null);
  const trendRef = useRef<HTMLInputElement>(null);
  const indexedRefs = [accidentRef, flagRef, eventRef, investigationRef, trendRef];


  // Logic to help the boxes sum to 100%
  const lastManualUpdatedIdx = useRef<number>(null);
  const lastAutoUpdatedIdx = useRef<number>(null);

  const changeBlurValue = (adjustedPanelIdx: number) => {
    // Note, since it starts on null, we need the strict equality check
    if (adjustedPanelIdx !== lastManualUpdatedIdx.current) {
      lastManualUpdatedIdx.current = adjustedPanelIdx;
      lastAutoUpdatedIdx.current = adjustedPanelIdx;
    }

    // Ensure that the value set fits within [0, 100]
    let newValue = Number(indexedRefs[adjustedPanelIdx].current.value);
    newValue = (newValue > 100)
      ? 100
      : (newValue < 0)
        ? 0
        : newValue;
    // TODO: find a prettier way of doing this
    indexedRefs[adjustedPanelIdx].current.value = newValue + '';

    let priorValue: number = riskDistribution[adjustedPanelIdx] * 100;
    let valueDifference: number = newValue - priorValue;
    const isIncrease: boolean = 0 < valueDifference;

    while (true) {
      lastAutoUpdatedIdx.current = lastAutoUpdatedIdx.current + 1;
      lastAutoUpdatedIdx.current = (lastAutoUpdatedIdx.current == lastManualUpdatedIdx.current)
        ? lastAutoUpdatedIdx.current + 1
        : lastAutoUpdatedIdx.current
      lastAutoUpdatedIdx.current = (lastAutoUpdatedIdx.current != indexedRefs.length)
        ? lastAutoUpdatedIdx.current
        : 0;

      const nextRefToUpdate = indexedRefs[lastAutoUpdatedIdx.current];
      const nextValueToUpdate = Number(nextRefToUpdate.current.value);
      if (isIncrease && nextValueToUpdate != 0) {
        nextRefToUpdate.current.value = (nextValueToUpdate - 1) + '';
        valueDifference = valueDifference - 1;
      }
      if (!isIncrease && nextValueToUpdate != 100) {
        nextRefToUpdate.current.value = (nextValueToUpdate + 1) + '';
        valueDifference = valueDifference + 1;
      }

      if (valueDifference == 0) break;
    }

    setCustomDistribution([
      (Number(accidentRef.current.value) / 100), (Number(flagRef.current.value) / 100),
      (Number(eventRef.current.value) / 100), (Number(investigationRef.current.value) / 100),
      (Number(trendRef.current.value) / 100)]);
  }

  const changeInputValue = (adjustedPanelIdx: number, triggerName: string) => {
    // This is a case where the user typing triggers a change in state. In this case, we'll eventually let onBlur handle it
    if (triggerName == 'insertText') return;

    const priorValue: number = riskDistribution[adjustedPanelIdx] * 100;
    const newValue: number = Number(indexedRefs[adjustedPanelIdx].current.value);
    const isIncrease: boolean = priorValue < newValue; 

    // Note, since it starts on null, we need the strict equality check
    if (adjustedPanelIdx !== lastManualUpdatedIdx.current) {
      lastManualUpdatedIdx.current = adjustedPanelIdx;
      lastAutoUpdatedIdx.current = adjustedPanelIdx;
    }

    while (true) {
      lastAutoUpdatedIdx.current = lastAutoUpdatedIdx.current + 1;
      lastAutoUpdatedIdx.current = (lastAutoUpdatedIdx.current == lastManualUpdatedIdx.current)
        ? lastAutoUpdatedIdx.current + 1
        : lastAutoUpdatedIdx.current
      lastAutoUpdatedIdx.current = (lastAutoUpdatedIdx.current != indexedRefs.length)
        ? lastAutoUpdatedIdx.current
        : 0;

      const nextRefToCheck = indexedRefs[lastAutoUpdatedIdx.current];
      if (isIncrease && nextRefToCheck.current.value != '0') break;
      if (!isIncrease && nextRefToCheck.current.value != '100') break;
    }

    const refToUpdate = indexedRefs[lastAutoUpdatedIdx.current];

    // TODO: Make those (string) setters prettier
    refToUpdate.current.value = isIncrease
      ? (Number(refToUpdate.current.value) - 1) + ''
      : (Number(refToUpdate.current.value) + 1) + '';

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
            <input onInput={e => changeInputValue(0, e.nativeEvent.inputType)} onBlur={_ => changeBlurValue(0)} 
              ref={accidentRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Flag Safety </div>
          <div>
            <input onInput={e => changeInputValue(1, e.nativeEvent.inputType)} onBlur={_ => changeBlurValue(1)} 
              ref={flagRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Event Entropy </div>
          <div>
            <input onInput={e => changeInputValue(2, e.nativeEvent.inputType)} onBlur={_ => changeBlurValue(2)}
              ref={eventRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Investigation </div>
          <div>
            <input onInput={e => changeInputValue(3, e.nativeEvent.inputType)} onBlur={_ => changeBlurValue(3)}
              ref={investigationRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
            <span className="risk-input-percentage">%</span>
          </div>
        </div>
        <div className='risk-input-container'>
          <div> Trend Slope </div>
          <div>
            <input onInput={e => changeInputValue(4, e.nativeEvent.inputType)} onBlur={_ => changeBlurValue(4)}
              ref={trendRef} type="number" min="0" max="100" defaultValue="20" disabled={!isCustom} />
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