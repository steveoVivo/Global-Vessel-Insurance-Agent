import getSelectionContext from './selectionContext';
import CountryPanelComponent from './countryPanelComponent';

/**
 * Wrapper component for handling the country control panel
 * @desc React - Component
 */
function ControlPanelComponent() {
  const { currentCountry } = getSelectionContext();

  if (!currentCountry) return null;

  return (
    <div className='right-panel'>
      <CountryPanelComponent />
    </div>
  );
}

export default ControlPanelComponent;
