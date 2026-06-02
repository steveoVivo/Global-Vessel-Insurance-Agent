import { useState } from 'react';

// TODO: Do I still need this here?
import 'ol/ol.css';

import getRiskContext from './riskContext';


function RiskSelectComponent() {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const { setDistribution } = getRiskContext();

  return (
    <div className='risk-select-component'      >
      <h4 onClick={() => setIsExpanded(!isExpanded)}>
        <span> Select Risk Factor </span>
        <span className='risk-select-dropdown-arrow'
          style={{ transform: isExpanded ? 'none' : 'rotate(180deg)' }}>
          ▼
        </span>
      </h4>
      <div style={{ display: isExpanded ? 'block' : 'none' }}>
        <button
          onClick={() => setDistribution('Accident_Risk')}
        >
          Display Accident Rate Risk
        </button>
        <button
          onClick={() => setDistribution('Flag_Risk')}
        >
          Display Flag Safety Risk
        </button>
        <button
          onClick={() => setDistribution('Event_Risk')}
        >
          Display Event Entropy Risk
        </button>
        <button
          onClick={() => setDistribution('Investigation_Risk')}
        >
          Display investigation Rate Risk
        </button>
        <button
          onClick={() => setDistribution('Trend_Risk')}
        >
          Display Risk from Trend Slope
        </button>
        <button
          onClick={() => {
            // Forces a re-render of components even if update is 'Custom' => 'Custom'
            setDistribution('Accident_Risk');
            setTimeout(() => setDistribution('Custom'), 0);
          }}
        >
          Custom Weighted Combination
        </button>
      </div>
    </div>
  );
}

export default RiskSelectComponent;