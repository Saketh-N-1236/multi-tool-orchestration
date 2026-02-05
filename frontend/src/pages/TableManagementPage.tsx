import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Plus, Trash2, Table as TableIcon, ArrowLeft, Edit, Loader2, Database } from 'lucide-react';
import { crudAPI } from '../services/api';
import type { Table, TableSchema, ColumnDefinition } from '../types/api';
import './TableManagementPage.css';

const TableManagementPage = () => {
  const { databaseName } = useParams<{ databaseName: string }>();
  const navigate = useNavigate();
  const [tables, setTables] = useState<Table[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newTableName, setNewTableName] = useState('');
  const [columns, setColumns] = useState<ColumnDefinition[]>([
    { name: 'id', type: 'INTEGER', primary_key: true, not_null: true },
  ]);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (databaseName) {
      loadTables();
    }
  }, [databaseName]);

  const loadTables = async () => {
    if (!databaseName) return;

    try {
      setLoading(true);
      setError(null);
      const data = await crudAPI.listTables(databaseName);
      setTables(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load tables');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTable = async () => {
    if (!databaseName || !newTableName.trim()) {
      setError('Table name is required');
      return;
    }

    if (columns.length === 0) {
      setError('At least one column is required');
      return;
    }

    try {
      setCreating(true);
      setError(null);
      await crudAPI.createTable(databaseName, newTableName.trim(), columns);
      setShowCreateModal(false);
      setNewTableName('');
      setColumns([{ name: 'id', type: 'INTEGER', primary_key: true, not_null: true }]);
      await loadTables();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create table');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteTable = async (tableName: string) => {
    if (!databaseName) return;

    if (!confirm(`Are you sure you want to delete table "${tableName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setError(null);
      await crudAPI.deleteTable(databaseName, tableName);
      await loadTables();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete table');
    }
  };

  const handleViewRows = (tableName: string) => {
    navigate(`/databases/${encodeURIComponent(databaseName!)}/tables/${encodeURIComponent(tableName)}/rows`);
  };

  const addColumn = () => {
    setColumns([...columns, { name: '', type: 'TEXT' }]);
  };

  const updateColumn = (index: number, field: keyof ColumnDefinition, value: any) => {
    const updated = [...columns];
    updated[index] = { ...updated[index], [field]: value };
    setColumns(updated);
  };

  const removeColumn = (index: number) => {
    setColumns(columns.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="table-management-page">
        <div className="loading-container">
          <Loader2 className="spinner" size={32} />
          <p>Loading tables...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="table-management-page">
      <div className="page-header">
        <div className="header-content">
          <button className="btn-back" onClick={() => navigate('/databases')}>
            <ArrowLeft size={20} />
            Back to Databases
          </button>
          <h1>
            <Database size={24} />
            {databaseName}
          </h1>
          <p>Manage tables in this database</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={20} />
          Create Table
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="tables-grid">
        {tables.length === 0 ? (
          <div className="empty-state">
            <TableIcon size={48} />
            <h3>No tables found</h3>
            <p>Create your first table to get started</p>
            <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={20} />
              Create Table
            </button>
          </div>
        ) : (
          tables.map((table) => (
            <div key={table.name} className="table-card">
              <div className="table-card-header">
                <TableIcon size={24} />
                <h3>{table.name}</h3>
              </div>
              <div className="table-card-body">
                <div className="table-stat">
                  <span>{table.column_count} column{table.column_count !== 1 ? 's' : ''}</span>
                </div>
                <div className="table-stat">
                  <span>{table.row_count} row{table.row_count !== 1 ? 's' : ''}</span>
                </div>
              </div>
              <div className="table-card-actions">
                <button className="btn-secondary" onClick={() => handleViewRows(table.name)}>
                  <Edit size={16} />
                  View Rows
                </button>
                <button className="btn-danger" onClick={() => handleDeleteTable(table.name)}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Table</h2>
            <div className="form-group">
              <label>Table Name</label>
              <input
                type="text"
                value={newTableName}
                onChange={(e) => setNewTableName(e.target.value)}
                placeholder="Enter table name (e.g., users)"
                autoFocus
              />
            </div>

            <div className="form-group">
              <div className="form-group-header">
                <label>Columns</label>
                <button type="button" className="btn-add-column" onClick={addColumn}>
                  <Plus size={16} />
                  Add Column
                </button>
              </div>
              <div className="columns-list">
                {columns.map((col, index) => (
                  <div key={index} className="column-row">
                    <input
                      type="text"
                      placeholder="Column name"
                      value={col.name}
                      onChange={(e) => updateColumn(index, 'name', e.target.value)}
                      className="column-name"
                    />
                    <select
                      value={col.type}
                      onChange={(e) => updateColumn(index, 'type', e.target.value)}
                      className="column-type"
                    >
                      <option value="INTEGER">INTEGER</option>
                      <option value="TEXT">TEXT</option>
                      <option value="REAL">REAL</option>
                      <option value="BLOB">BLOB</option>
                      <option value="NUMERIC">NUMERIC</option>
                    </select>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={col.primary_key || false}
                        onChange={(e) => updateColumn(index, 'primary_key', e.target.checked)}
                      />
                      PK
                    </label>
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={col.not_null || false}
                        onChange={(e) => updateColumn(index, 'not_null', e.target.checked)}
                      />
                      NOT NULL
                    </label>
                    <button
                      type="button"
                      className="btn-remove-column"
                      onClick={() => removeColumn(index)}
                      disabled={columns.length === 1}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowCreateModal(false)} disabled={creating}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleCreateTable}
                disabled={creating || !newTableName.trim() || columns.some((c) => !c.name.trim())}
              >
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

export default TableManagementPage;
