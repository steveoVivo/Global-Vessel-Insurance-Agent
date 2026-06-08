import { useState } from 'react';

// TODO: Do I still need this here?
import 'ol/ol.css';

import getRiskContext from './riskContext';
import getPanelContext from './panelContext';

/**
 * Component used to modify the weights of the different risk scores
 * @desc React - Component
 */
function RiskSelectComponent() {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const { riskDistributionName, setDistribution } = getRiskContext();
  // TODO: Phase this out, it never gets changed now
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
          className={(riskDistributionName == 'Event_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Event_Risk'}
          onClick={() => setDistribution('Event_Risk')}
        >
          Display Event Entropy Risk
        </button>
        <button
          className={(riskDistributionName == 'Ship_Type_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Ship_Type_Risk'}
          onClick={() => setDistribution('Ship_Type_Risk')}
        >
          Display Ship Type Risk
        </button>
        <button
          className={(riskDistributionName == 'Open_Sea_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Open_Sea_Risk'}
          onClick={() => setDistribution('Open_Sea_Risk')}
        >
          Display Open Sea Risk
        </button>
        <button
          className={(riskDistributionName == 'Fleet_Volatility_Risk') ? 'current-selected-button' : ''}
          disabled={riskDistributionName == 'Fleet_Volatility_Risk'}
          onClick={() => setDistribution('Fleet_Volatility_Risk')}
        >
          Display Fleet Volatility Risk
        </button>
        <button
          className={(riskDistributionName == 'Custom') ? 'current-selected-button' : ''}
          disabled={(riskDistributionName == 'Custom') && (activePanel == 'Custom_Risk')}
          onClick={() => setDistribution('Custom')}
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
