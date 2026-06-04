import { useState } from 'react';

// TODO: Do I still need this here?
import 'ol/ol.css';

import getRiskContext from './riskContext';
import getPanelContext from './panelContext';


function RiskSelectComponent() {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const { riskDistributionName, setDistribution } = getRiskContext();
  const { activePanel } = getPanelContext();

  const riskSelectComponentClassname = 'risk-select-component' + ((isExpanded) ? ' expanded' : '');

  return (
    <div className={riskSelectComponentClassname}>
      <h4 onClick={() => setIsExpanded(!isExpanded)}>
        <span> Select Risk Factor </span>
        <span className='risk-select-dropdown-arrow'
          style={{ transform: isExpanded ? 'none' : 'rotate(180deg)' }}>
          ▼
        </span>
      </h4>
      <div style={{ display: isExpanded ? 'block' : 'none' }}>
        <button
          className={(riskDistributionName == 'Accident_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Accident_Risk'}
          onClick={() => setDistribution('Accident_Risk')}
        >
          Display Accident Rate Risk
        </button>
        <button
          className={(riskDistributionName == 'Flag_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Flag_Risk'}
          onClick={() => setDistribution('Flag_Risk')}
        >
          Display Flag Safety Risk
        </button>
        <button
          className={(riskDistributionName == 'Event_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Event_Risk'}
          onClick={() => setDistribution('Event_Risk')}
        >
          Display Event Entropy Risk
        </button>
        <button
          className={(riskDistributionName == 'Investigation_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Investigation_Risk'}
          onClick={() => setDistribution('Investigation_Risk')}
        >
          Display investigation Rate Risk
        </button>
        <button
          className={(riskDistributionName == 'Trend_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Trend_Risk'}
          onClick={() => setDistribution('Trend_Risk')}
        >
          Display Risk from Trend Slope
        </button>
        <button
          className={(riskDistributionName == 'Custom') ? 'current-selected-button' : ''}
          disabled={(riskDistributionName == 'Custom') && (activePanel == 'Custom_Risk')}
          onClick={() => {
            // Forces a re-render of components even if update is 'Custom' => 'Custom'
            setDistribution('Accident_Risk');
            setTimeout(() => setDistribution('Custom'), 0);
          }}
        >
          {(riskDistributionName == 'Custom' && (activePanel != 'Custom_Risk')) 
            ? '[Open Custom Control Panel]'
            :'Custom Weighted Combination'}
        </button>
      </div>
    </div>
  );
}

export default RiskSelectComponent;