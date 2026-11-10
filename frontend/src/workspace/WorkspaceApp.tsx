import { Route, Routes } from 'react-router-dom'
import { WorkspaceProvider } from '../state/Workspace'
import { Shell } from './Shell'
import Overview from './Overview'
import DataHub from './DataHub'
import Quality from './Quality'
import Eda from './Eda'
import Dashboard from './Dashboard'
import Forecast from './Forecast'
import Insights from './Insights'
import Reports from './Reports'

export default function WorkspaceApp() {
  return (
    <WorkspaceProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<Overview />} />
          <Route path="data" element={<DataHub />} />
          <Route path="quality" element={<Quality />} />
          <Route path="eda" element={<Eda />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="forecast" element={<Forecast />} />
          <Route path="insights" element={<Insights />} />
          <Route path="reports" element={<Reports />} />
          <Route path="*" element={<Overview />} />
        </Route>
      </Routes>
    </WorkspaceProvider>
  )
}
