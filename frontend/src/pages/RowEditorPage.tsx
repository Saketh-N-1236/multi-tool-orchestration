import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Plus, Trash2, Edit, ArrowLeft, Save, X, Loader2, Table } from 'lucide-react';
import { crudAPI } from '../services/api';
import type { Row, RowListResponse, TableSchema } from '../types/api';
import './RowEditorPage.css';

const RowEditorPage = () => {
  const { databaseName, tableName } = useParams<{ databaseName: string; tableName: string }>();
  const navigate = useNavigate();
  const [rows, setRows] = useState<Row[]>([]);
  const [tableSchema, setTableSchema] = useState<TableSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingRow, setEditingRow] = useState<Row | null>(null);
  const [newRowData, setNewRowData] = useState<Record<string, any>>({});
  const [saving, setSaving] = useState(false);
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [whereClause, setWhereClause] = useState('');

  useEffect(() => {
    if (databaseName && tableName) {
      loadTableSchema();
      loadRows();
    }
  }, [databaseName, tableName, limit, offset, whereClause]);

  const loadTableSchema = async () => {
    if (!databaseName || !tableName) return;

    try {
      const data = await crudAPI.getTable(databaseName, tableName);
      setTableSchema(data.schema);
    } catch (err: any) {
      console.error('Failed to load table schema:', err);
    }
  };

  const loadRows = async () => {
    if (!databaseName || !tableName) return;

    try {
      setLoading(true);
      setError(null);
      const data: RowListResponse = await crudAPI.listRows(
        databaseName,
        tableName,
        limit,
        offset,
        whereClause || undefined
      );
      setRows(data.rows);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to load rows');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRow = async () => {
    if (!databaseName || !tableName) return;

    try {
      setSaving(true);
      setError(null);
      await crudAPI.insertRow(databaseName, tableName, newRowData);
      setShowCreateModal(false);
      setNewRowData({});
      await loadRows();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to create row');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateRow = async (rowId: number) => {
    if (!databaseName || !tableName) return;

    try {
      setSaving(true);
      setError(null);
      await crudAPI.updateRow(databaseName, tableName, rowId, editingRow!);
      setEditingRow(null);
      await loadRows();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to update row');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteRow = async (rowId: number) => {
    if (!databaseName || !tableName) return;

    if (!confirm(`Are you sure you want to delete this row? This action cannot be undone.`)) {
      return;
    }

    try {
      setError(null);
      await crudAPI.deleteRow(databaseName, tableName, rowId);
      await loadRows();
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete row');
    }
  };

  const startEdit = (row: Row) => {
    const rowId = row.rowid || row.id;
    setEditingRow({ ...row, rowid: rowId });
  };

  const cancelEdit = () => {
    setEditingRow(null);
  };

  const updateEditingRow = (field: string, value: any) => {
    if (editingRow) {
      setEditingRow({ ...editingRow, [field]: value });
    }
  };

  const updateNewRowData = (field: string, value: any) => {
    setNewRowData({ ...newRowData, [field]: value });
  };

  const handleFilter = () => {
    setOffset(0);
    loadRows();
  };

  const clearFilter = () => {
    setWhereClause('');
    setOffset(0);
  };

  if (loading && rows.length === 0) {
    return (
      <div className="row-editor-page">
        <div className="loading-container">
          <Loader2 className="spinner" size={32} />
          <p>Loading rows...</p>
        </div>
      </div>
    );
  }

  const columns = tableSchema?.columns || [];
  const nonPrimaryColumns = columns.filter((col) => !col.primary_key);

  return (
    <div className="row-editor-page">
      <div className="page-header">
        <div className="header-content">
          <button
            className="btn-back"
            onClick={() => navigate(`/databases/${encodeURIComponent(databaseName!)}/tables`)}
          >
            <ArrowLeft size={20} />
            Back to Tables
          </button>
          <h1>
            <Table size={24} />
            {tableName}
          </h1>
          <p>{total} row{total !== 1 ? 's' : ''} total</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={20} />
          Add Row
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="filters-section">
        <div className="filter-group">
          <label>Filter (WHERE clause):</label>
          <div className="filter-input-group">
            <input
              type="text"
              value={whereClause}
              onChange={(e) => setWhereClause(e.target.value)}
              placeholder="e.g., age=30 or name='John'"
              onKeyPress={(e) => e.key === 'Enter' && handleFilter()}
            />
            <button className="btn-secondary" onClick={handleFilter}>
              Apply
            </button>
            {whereClause && (
              <button className="btn-secondary" onClick={clearFilter}>
                Clear
              </button>
            )}
          </div>
        </div>
        <div className="pagination-controls">
          <label>
            Limit:
            <input
              type="number"
              min="1"
              max="1000"
              value={limit}
              onChange={(e) => {
                setLimit(Number(e.target.value));
                setOffset(0);
              }}
            />
          </label>
          <div className="pagination-buttons">
            <button
              className="btn-secondary"
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
            >
              Previous
            </button>
            <span>
              Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
            </span>
            <button
              className="btn-secondary"
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.name}>{col.name}</th>
              ))}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} className="empty-cell">
                  No rows found
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => {
                const rowId = row.rowid || row.id || rowIndex;
                const isEditing = editingRow?.rowid === rowId;

                return (
                  <tr key={rowId}>
                    {columns.map((col) => {
                      if (isEditing && !col.primary_key) {
                        return (
                          <td key={col.name}>
                            <input
                              type={col.type === 'INTEGER' || col.type === 'REAL' ? 'number' : 'text'}
                              value={editingRow[col.name] ?? ''}
                              onChange={(e) =>
                                updateEditingRow(
                                  col.name,
                                  col.type === 'INTEGER' ? parseInt(e.target.value) || 0 : e.target.value
                                )
                              }
                              className="inline-edit-input"
                            />
                          </td>
                        );
                      }
                      return <td key={col.name}>{row[col.name] ?? 'NULL'}</td>;
                    })}
                    <td>
                      {isEditing ? (
                        <div className="action-buttons">
                          <button className="btn-success" onClick={() => handleUpdateRow(rowId)} disabled={saving}>
                            {saving ? <Loader2 className="spinner" size={16} /> : <Save size={16} />}
                          </button>
                          <button className="btn-secondary" onClick={cancelEdit} disabled={saving}>
                            <X size={16} />
                          </button>
                        </div>
                      ) : (
                        <div className="action-buttons">
                          <button className="btn-secondary" onClick={() => startEdit(row)}>
                            <Edit size={16} />
                          </button>
                          <button className="btn-danger" onClick={() => handleDeleteRow(rowId)}>
                            <Trash2 size={16} />
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <h2>Add New Row</h2>
            <div className="form-fields">
              {nonPrimaryColumns.map((col) => (
                <div key={col.name} className="form-group">
                  <label>
                    {col.name} {col.not_null && <span className="required">*</span>}
                  </label>
                  <input
                    type={col.type === 'INTEGER' || col.type === 'REAL' ? 'number' : 'text'}
                    value={newRowData[col.name] ?? ''}
                    onChange={(e) =>
                      updateNewRowData(
                        col.name,
                        col.type === 'INTEGER' ? parseInt(e.target.value) || 0 : e.target.value
                      )
                    }
                    placeholder={col.type}
                    required={col.not_null}
                  />
                </div>
              ))}
            </div>
            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowCreateModal(false)} disabled={saving}>
                Cancel
              </button>
              <button
                className="btn-primary"
                onClick={handleCreateRow}
                disabled={saving || nonPrimaryColumns.some((col) => col.not_null && !newRowData[col.name])}
              >
                {saving ? <Loader2 className="spinner" size={16} /> : <Plus size={16} />}
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RowEditorPage;
