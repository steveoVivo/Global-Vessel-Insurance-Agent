import { useState, useEffect } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import heroImg from './assets/hero.png'
import './App.css'

function App() {
  // TODO: Type the useState once you find out why templates are being so weird
  const [data, setData] = useState(['Empty Array']);

  useEffect(() => {
      // No need for http://localhost:5000 because of the Vite proxy
      fetch('/api/data')
        .then(res => res.json())
        .then(data => console.log(data.message))
        .catch(err => console.error(err))
    }, []);

  return (
    <div>
      hi
    </div>
  )
}

export default App
