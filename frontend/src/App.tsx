import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Consumption from './pages/Consumption'
import Reconciliation from './pages/Reconciliation'
import Tariffs from './pages/Tariffs'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="upload" element={<Upload />} />
        <Route path="consumption" element={<Consumption />} />
        <Route path="reconciliation" element={<Reconciliation />} />
        <Route path="tariffs" element={<Tariffs />} />
      </Route>
    </Routes>
  )
}

export default App
