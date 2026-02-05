import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Trash2, Database, Table, ArrowRight, Loader2 } from 'lucide-react';
import { crudAPI } from '../services/api';
import type { Database as DatabaseType } from '../types/api';
import './DatabaseManagementPage.css';

const DatabaseManagementPage = () => {
  const [databases, setDatabases] = useState<DatabaseType[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newDbName, setNewDbName] = useState('');
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    loadDatabases();
  }, []);

  const loadDatabases = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await crudAPI.listDatabases();
      setDatabases(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load databases');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDatabase = async () => {
    if (!newDbName.trim()) {
      setError('Database name is required');
      return;
    }

    try {
      setCreating(true);
      setError(null);
      await crudAPI.createDatabase(newDbName.trim(), 'sqlite');
      setShowCreateModal(false);
      setNewDbName('');
      await loadDatabases();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create database');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteDatabase = async (name: string) => {
    if (name === 'main') {
      setError('Cannot delete the main database');
      return;
    }

    if (!confirm(`Are you sure you want to delete database "${name}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setError(null);
      await crudAPI.deleteDatabase(name);
      await loadDatabases();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete database');
    }
  };

  const handleViewTables = (dbName: string) => {
    navigate(`/databases/${encodeURIComponent(dbName)}/tables`);
  };

  if (loading) {
    return (
      <div className="database-management-page">
        <div className="loading-container">
          <Loader2 className="spinner" size={32} />
          <p>Loading databases...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="database-management-page">
      <div className="page-header">
        <div className="header-content">
          <h1>Database Management</h1>
          <p>Create, view, and manage databases</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={20} />
          Create Database
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="databases-grid">
        {databases.length === 0 ? (
          <div className="empty-state">
            <Database size={48} />
            <h3>No databases found</h3>
            <p>Create your first database to get started</p>
            <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={20} />
              Create Database
            </button>
          </div>
        ) : (
          databases.map((db) => (
            <div key={db.name} className="database-card">
              <div className="database-card-header">
                <Database size={24} />
                <h3>{db.name}</h3>
                {db.name === 'main' && <span className="badge">Default</span>}
              </div>
              <div className="database-card-body">
                <div className="database-stat">
                  <Table size={16} />
                  <span>{db.table_count} table{db.table_count !== 1 ? 's' : ''}</span>
                </div>
                <div className="database-stat">
                  <span>Type: {db.type}</span>
                </div>
              </div>
              <div className="database-card-actions">
                <button
                  className="btn-secondary"
                  onClick={() => handleViewTables(db.name)}
                >
                  View Tables
                  <ArrowRight size={16} />
                </button>
                <button
                  className="btn-danger"
                  onClick={() => handleDeleteDatabase(db.name)}
                  disabled={db.name === 'main'}
                  title={db.name === 'main' ? 'Cannot delete main database' : 'Delete database'}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Database</h2>
            <div className="form-group">
              <label>Database Name</label>
              <input
                type="text"
                value={newDbName}
                onChange={(e) => setNewDbName(e.target.value)}
                placeholder="Enter database name (e.g., analytics)"
                onKeyPress={(e) => e.key === 'Enter' && handleCreateDatabase()}
                autoFocus
              />
              <small>Must start with a letter and contain only alphanumeric characters and underscores</small>
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowCreateModal(false)} disabled={creating}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleCreateDatabase} disabled={creating || !newDbName.trim()}>
                {creating ? <Loader2 className="spinner" size={16} /> : <Plus size={16} />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DatabaseManagementPage;
