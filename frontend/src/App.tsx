import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import MainLayout from './components/Layout/MainLayout';
import ChatPage from './pages/ChatPage';
import InferenceLoggerPage from './pages/InferenceLoggerPage';
import MLLoggerPage from './pages/MLLoggerPage';
import DocumentsPage from './pages/DocumentsPage';
import ToolsPage from './pages/ToolsPage';
import DatabaseManagementPage from './pages/DatabaseManagementPage';
import TableManagementPage from './pages/TableManagementPage';
import RowEditorPage from './pages/RowEditorPage';

function App() {
  return (
    <Router>
      <MainLayout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/inference-logger" element={<InferenceLoggerPage />} />
          <Route path="/ml-logger" element={<MLLoggerPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/tools" element={<ToolsPage />} />
          <Route path="/databases" element={<DatabaseManagementPage />} />
          <Route path="/databases/:databaseName/tables" element={<TableManagementPage />} />
          <Route path="/databases/:databaseName/tables/:tableName/rows" element={<RowEditorPage />} />
        </Routes>
      </MainLayout>
    </Router>
  );
}

export default App;
