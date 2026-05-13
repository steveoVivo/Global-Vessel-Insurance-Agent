import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

const starterText = "If you see this message, your React app is working. This message should be replaced momentarily.";

function App() {
  // TODO: Type the useState once you find out why templates are being so weird
  const [data, setData] = useState(starterText);

  useEffect(() => {
      // '/api' retrieves data from the Vite Proxy
      fetch('/api/data')
        .then(res => res.json())
        .then(data => setData(data.message))
        .catch(err => console.error(err))
    }, []);

  return (
    <div>
      {data}
    </div>
  )
}

export default App
