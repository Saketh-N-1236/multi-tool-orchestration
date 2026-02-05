import { useState, useEffect, useRef } from 'react';
import { Upload, FileText, Trash2, Search, Plus, X } from 'lucide-react';
import { documentsAPI } from '../services/api';
import './DocumentsPage.css';

const DocumentsPage = () => {
  const [collections, setCollections] = useState<string[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showUploadForm, setShowUploadForm] = useState(false);
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [createCollectionName, setCreateCollectionName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await documentsAPI.getCollections();
      const collectionsList = response.collections || [];
      // Normalize collections - handle both string and object formats
      const normalizedCollections = collectionsList.map((col: any) => {
        if (typeof col === 'string') {
          return col;
        }
        if (typeof col === 'object' && col !== null) {
          // Handle object format: { name: "...", document_count: ... }
          return col.name || col.collection_name || String(col);
        }
        return String(col || '');
      }).filter((col: string) => col && col.length > 0);
      
      setCollections(normalizedCollections);
      if (normalizedCollections.length > 0 && !selectedCollection) {
        setSelectedCollection(normalizedCollections[0]);
      }
    } catch (error: any) {
      console.error('Failed to load collections:', error);
      setError(error.response?.data?.detail || error.message || 'Failed to load collections');
      if (error.response?.status === 500) {
        setError('Vector search server may not be running. Please start the MCP servers.');
      }
      setCollections([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
    }
  };

  const handleFileUpload = async () => {
    if (!selectedFile) {
      alert('Please select a file to upload');
      return;
    }

    let collectionName = '';
    if (showCreateCollection) {
      collectionName = createCollectionName.trim();
      if (!collectionName) {
        alert('Please enter a collection name');
        return;
      }
      // Validate collection name format
      if (collectionName.length < 3 || collectionName.length > 63) {
        alert('Collection name must be between 3 and 63 characters');
        return;
      }
      if (!/^[a-zA-Z0-9]([a-zA-Z0-9_-]*[a-zA-Z0-9])?$/.test(collectionName)) {
        alert('Collection name must start and end with alphanumeric characters. Only letters, numbers, underscores, and hyphens are allowed.');
        return;
      }
    } else {
      collectionName = selectedCollection || '';
      if (!collectionName) {
        alert('Please select a collection');
        return;
      }
    }

    setUploading(true);
    try {
      await documentsAPI.uploadFile(selectedFile, collectionName);
      alert(`File uploaded successfully to collection "${collectionName}"!`);
      setSelectedFile(null);
      setCreateCollectionName('');
      setShowCreateCollection(false);
      setShowUploadForm(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      loadCollections();
    } catch (error: any) {
      alert(`Upload failed: ${error.response?.data?.detail || error.message || 'Failed to upload file'}`);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteCollection = async (collectionName: string) => {
    if (!window.confirm(`Are you sure you want to delete collection "${collectionName}"? This will permanently delete all documents in this collection.`)) {
      return;
    }

    try {
      await documentsAPI.deleteCollection(collectionName);
      alert(`Collection "${collectionName}" deleted successfully!`);
      if (selectedCollection === collectionName) {
        setSelectedCollection('');
      }
      loadCollections();
    } catch (error: any) {
      alert(`Delete failed: ${error.response?.data?.detail || error.message || 'Failed to delete collection'}`);
    }
  };

  return (
    <div className="documents-page">
      <div className="documents-header">
        <div>
          <h1>Documents</h1>
          <p>Upload files to vector collections (JSON or PDF)</p>
        </div>
        <button className="primary-button" onClick={() => setShowUploadForm(!showUploadForm)}>
          <Upload size={20} />
          Upload File
        </button>
      </div>

      {showUploadForm && (
        <div className="upload-form-card">
          <h2>Upload File</h2>
          <div className="form-group">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label>Collection</label>
              <button
                type="button"
                className="secondary-button"
                style={{ padding: '6px 12px', fontSize: '12px' }}
                onClick={() => setShowCreateCollection(!showCreateCollection)}
              >
                {showCreateCollection ? 'Select Existing' : '+ Create New'}
              </button>
            </div>
            {showCreateCollection ? (
              <input
                type="text"
                placeholder="Enter new collection name (3-63 chars, alphanumeric)"
                value={createCollectionName}
                onChange={(e) => setCreateCollectionName(e.target.value)}
                className="form-input"
              />
            ) : (
              <select
                value={selectedCollection}
                onChange={(e) => setSelectedCollection(e.target.value)}
                className="form-input"
              >
                <option value="">Select a collection</option>
                {collections.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
            )}
            {showCreateCollection && (
              <p style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                Collections are created automatically when you upload files. Use alphanumeric characters, underscores, or hyphens.
              </p>
            )}
          </div>

          <div className="form-group">
            <label>File</label>
            <div className="file-upload-area">
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.pdf"
                onChange={handleFileSelect}
                className="file-input"
                id="file-upload"
              />
              <label htmlFor="file-upload" className="file-upload-label">
                <Upload size={24} />
                <span>{selectedFile ? selectedFile.name : 'Choose JSON or PDF file'}</span>
              </label>
              {selectedFile && (
                <button
                  type="button"
                  className="remove-file-button"
                  onClick={() => {
                    setSelectedFile(null);
                    if (fileInputRef.current) {
                      fileInputRef.current.value = '';
                    }
                  }}
                >
                  <X size={16} />
                </button>
              )}
            </div>
            <p style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
              Supported formats: JSON (array of documents) or PDF (text will be extracted)
            </p>
          </div>

          <div className="form-actions">
            <div className="form-actions-right">
              <button
                className="secondary-button"
                onClick={() => {
                  setShowUploadForm(false);
                  setShowCreateCollection(false);
                  setCreateCollectionName('');
                  setSelectedFile(null);
                  if (fileInputRef.current) {
                    fileInputRef.current.value = '';
                  }
                }}
              >
                Cancel
              </button>
              <button
                className="primary-button"
                onClick={handleFileUpload}
                disabled={uploading || !selectedFile}
              >
                {uploading ? 'Uploading...' : 'Upload File'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="collections-section">
        <div className="section-header">
          <h2>Collections</h2>
          <div className="search-box">
            <Search size={18} />
            <input
              type="text"
              placeholder="Search collections..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        <div className="collections-grid">
          {collections
            .filter((col) => {
              const colStr = typeof col === 'string' ? col : String(col || '');
              return colStr.toLowerCase().includes(searchQuery.toLowerCase());
            })
            .map((collection) => {
              const collectionStr = typeof collection === 'string' ? collection : String(collection || '');
              return (
                <div
                  key={collectionStr}
                  className={`collection-card ${selectedCollection === collectionStr ? 'active' : ''}`}
                >
                  <div className="collection-card-content" onClick={() => setSelectedCollection(collectionStr)}>
                    <FileText size={24} />
                    <h3>{collectionStr}</h3>
                    <p>Click to select</p>
                  </div>
                  <button
                    className="delete-collection-button"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteCollection(collectionStr);
                    }}
                    title="Delete collection"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })}
        </div>

        {loading && (
          <div className="empty-state">
            <p>Loading collections...</p>
          </div>
        )}
        {error && !loading && (
          <div className="empty-state">
            <h3 style={{ color: '#ef4444' }}>Error</h3>
            <p>{error}</p>
            <button className="retry-button" onClick={loadCollections} style={{ marginTop: '12px' }}>
              Retry
            </button>
          </div>
        )}
        {!loading && !error && collections.length === 0 && (
          <div className="empty-state">
            <FileText size={48} />
            <h3>No collections found</h3>
            <p>Collections are created automatically when you upload files.</p>
            <p style={{ marginTop: '8px', fontSize: '14px' }}>
              Click "Upload File" to get started.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentsPage;
