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

  const customRiskHeaderClassname = 'control-panel-header' + ((activePanel != 'Custom_Risk') ? ' control-panel-header-hoverable' : '');
  const countryPanelHeaderClassname = 'control-panel-header' + ((activePanel != 'Selected_Country') ? ' control-panel-header-hoverable' : '');
  

  return (
    <div className='vessel-control-panel'>
      <div className='control-panel-container' onClick={() => setActivePanel('Custom_Risk')}>
        <div className={customRiskHeaderClassname}> Custom Risk {(activePanel == 'Custom_Risk') ? '▲' : '▼'} </div>
        <div className='control-panel-content' style={{height: (activePanel == 'Custom_Risk') ? 'auto' : '0px', overflow: 'hidden'}}>
          <CustomriskPanelComponent />
        </div>
      </div>
      <div className='control-panel-container' onClick={() => setActivePanel('Selected_Country')}>
        <div className={countryPanelHeaderClassname}> 
          Selected Country {(activePanel == 'Selected_Country') ? '▲' : '▼'} 
        </div>
        <div className='control-panel-content' style={{display: (activePanel == 'Selected_Country') ? 'block' : 'none', overflow: 'hidden'}}>
          <CountryPanelComponent />
        </div>
      </div>
    </div>
  );
}

export default ControlPanelComponent;