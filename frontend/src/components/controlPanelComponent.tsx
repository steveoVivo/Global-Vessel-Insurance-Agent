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

  // TODO: I think that you can collapse all of this (all 6) into a single classname for the container object, then work the CSS around that.
  const customRiskContainerClassname = 'control-panel-container' + ((activePanel == 'Custom_Risk') ? ' control-panel-expanded' : '');
  const countryPanelContainerClassname = 'control-panel-container' + ((activePanel == 'Selected_Country') ? ' control-panel-expanded' : '');

  const customRiskHeaderClassname = 'control-panel-header' + ((activePanel != 'Custom_Risk') ? ' control-panel-header-hoverable' : '');
  const countryPanelHeaderClassname = 'control-panel-header' + ((activePanel != 'Selected_Country') ? ' control-panel-header-hoverable' : '');
  
  const customRiskBodyClassname = 'control-panel-content' + ((activePanel != 'Custom_Risk') ? ' hidden' : '');
  const countryPanelBodyClassname = 'control-panel-content' + ((activePanel != 'Selected_Country') ? ' hidden' : '');
  

  return (
    <div className='vessel-control-panel'>
      <div className={customRiskContainerClassname} onClick={() => setActivePanel('Custom_Risk')}>
        <div className={customRiskHeaderClassname}> Custom Risk {(activePanel == 'Custom_Risk') ? '▲' : '▼'} </div>
        <div className={customRiskBodyClassname}>
          <CustomriskPanelComponent />
        </div>
      </div>
      <div className={countryPanelContainerClassname} onClick={() => setActivePanel('Selected_Country')}>
        <div className={countryPanelHeaderClassname}> 
          Selected Country {(activePanel == 'Selected_Country') ? '▲' : '▼'} 
        </div>
        <div className={countryPanelBodyClassname}>
          <CountryPanelComponent />
        </div>
      </div>
    </div>
  );
}

export default ControlPanelComponent;