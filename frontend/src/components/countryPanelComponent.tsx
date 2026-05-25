// TODO: Do I still need this here?
import 'ol/ol.css';

import getSelectionContext from './selectionContext';

function CountryPanelComponent() {
  const { currentCountry } = getSelectionContext();

  const countryText = currentCountry != 'United States'
    ? currentCountry
    : '~!~ OLD GLORY ~!~ 🦅🦅🇺🇸'

  return (
    <div>
        <span style={{display: (currentCountry == null) ? 'none' : 'block'}}> Currently Selected Country: {countryText} </span>
        <span style={{display: (currentCountry != null) ? 'none' : 'block', color: 'darkslategray'}}> [No country currently selected] </span>
    </div>
  );
}

export default CountryPanelComponent;