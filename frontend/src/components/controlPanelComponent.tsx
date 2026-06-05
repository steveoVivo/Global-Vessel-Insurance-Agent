import getSelectionContext from './selectionContext';
import CountryPanelComponent from './countryPanelComponent';

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
