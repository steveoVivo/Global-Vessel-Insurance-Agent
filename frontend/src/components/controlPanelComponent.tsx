import { useEffect, useState } from 'react';

import CountryPanelComponent from './countryPanelComponent';
import CustomriskPanelComponent from './customriskPanelComponent';

import getSelectionContext from './selectionContext';
import getRiskContext from './riskContext';

export type ActivePanels = 'Selected_Country' | 'Custom_Risk';

function ControlPanelComponent() {
  const [activePanel, setActivePanel] = useState<ActivePanels>('Custom_Risk');

  const { currentCountry } = getSelectionContext();
  const { riskDistributionName } = getRiskContext();

  useEffect(() => {
    if (!currentCountry) return;
    setActivePanel('Selected_Country');
  }, [currentCountry]);

  useEffect(() => {
    if (riskDistributionName != 'Custom') return;
    setActivePanel('Custom_Risk');
  }, [riskDistributionName]);
  

  return (
    <div className='vessel-control-panel'>
      <div>
        <div style={{height: '20px'}}> Custom Risk {(activePanel == 'Custom_Risk') ? '▲' : '▼'} </div>
        <div style={{height: (activePanel == 'Custom_Risk') ? 'auto' : '0px', overflow: 'hidden'}}>
          <CustomriskPanelComponent />
        </div>
        <div style={{height: '20px'}}> Selected Country {(activePanel == 'Selected_Country') ? '▲' : '▼'} </div>
        <div style={{height: (activePanel == 'Selected_Country') ? 'auto' : '0px', overflow: 'hidden'}}>
          <CountryPanelComponent />
        </div>
      </div>
    </div>
  );
}

export default ControlPanelComponent;