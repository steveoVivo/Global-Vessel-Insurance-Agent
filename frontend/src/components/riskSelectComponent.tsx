// TODO: Do I still need this here?
import 'ol/ol.css';

import getRiskContext from './riskContext';


function RiskSelectComponent() {
  const { setDistribution } = getRiskContext();

  return (
    <div 
        style={{
          position: 'absolute',
          right: '3px',
          top: '3px',
          zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          padding: '2px',
          paddingBottom: '10px',
          borderRadius: '12px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.2)',
          minWidth: 200,
          maxWidth: '20%'
        }}
      >
        <h4> Select Risk Factor </h4>
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
            onClick={() => setDistribution('Severity_Risk')}
        >
            Display Severity Risk
        </button>
        <button
            onClick={() => setDistribution('Ship_Risk')}
        >
            Display Ship Type Risk
        </button>
        <button
            onClick={() => setDistribution('Custom')}
        >
            Custom Weighted Combination
        </button>
    </div>
  );
}

export default RiskSelectComponent;