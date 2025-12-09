import { useState, useEffect } from 'react';
import './WorkspaceSettings.css';

export default function WorkspaceSettings({ workspace, onClose }) {
  const [documents, setDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  // Form state for document upload
  const [uploadForm, setUploadForm] = useState({
    title: '',
    content: '',
    source: ''
  });

  useEffect(() => {
    fetchDocuments();
    fetchStats();
  }, [workspace]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8001/api/workspaces/${workspace}/documents`);
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch(`http://localhost:8001/api/workspaces/${workspace}/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();

    if (!uploadForm.title || !uploadForm.content) {
      setError('Title and content are required');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8001/api/workspaces/${workspace}/documents`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(uploadForm)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const result = await response.json();

      // Reset form
      setUploadForm({ title: '', content: '', source: '' });

      // Refresh documents and stats
      await fetchDocuments();
      await fetchStats();

      alert(`Document uploaded successfully! Created ${result.chunks_created} chunk(s).`);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId) => {
    if (!confirm('Are you sure you want to delete this document?')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8001/api/workspaces/${workspace}/documents/${docId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        await fetchDocuments();
        await fetchStats();
      } else {
        alert('Failed to delete document');
      }
    } catch (err) {
      console.error('Failed to delete document:', err);
      alert('Failed to delete document');
    }
  };

  return (
    <div className="workspace-settings-overlay" onClick={onClose}>
      <div className="workspace-settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{workspace} - Workspace Settings</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {/* Stats Section */}
          {stats && (
            <div className="stats-section">
              <h3>Knowledge Base Statistics</h3>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Documents</div>
                  <div className="stat-value">{stats.document_count || 0}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Vector Size</div>
                  <div className="stat-value">{stats.vector_size || 0}</div>
                </div>
              </div>
            </div>
          )}

          {/* Upload Section */}
          <div className="upload-section">
            <h3>Upload Document</h3>
            <form onSubmit={handleUpload} className="upload-form">
              <div className="form-group">
                <label htmlFor="title">Document Title *</label>
                <input
                  id="title"
                  type="text"
                  value={uploadForm.title}
                  onChange={(e) => setUploadForm({ ...uploadForm, title: e.target.value })}
                  placeholder="e.g., Project Requirements"
                  disabled={uploading}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="source">Source (optional)</label>
                <input
                  id="source"
                  type="text"
                  value={uploadForm.source}
                  onChange={(e) => setUploadForm({ ...uploadForm, source: e.target.value })}
                  placeholder="e.g., https://example.com/doc"
                  disabled={uploading}
                />
              </div>

              <div className="form-group">
                <label htmlFor="content">Content *</label>
                <textarea
                  id="content"
                  value={uploadForm.content}
                  onChange={(e) => setUploadForm({ ...uploadForm, content: e.target.value })}
                  placeholder="Paste document content here..."
                  rows={12}
                  disabled={uploading}
                  required
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <button type="submit" className="upload-button" disabled={uploading}>
                {uploading ? 'Uploading...' : 'Upload Document'}
              </button>
            </form>
          </div>

          {/* Documents List */}
          <div className="documents-section">
            <h3>Uploaded Documents</h3>

            {loading ? (
              <div className="loading-message">Loading documents...</div>
            ) : documents.length === 0 ? (
              <div className="empty-message">
                No documents uploaded yet. Upload documents to enable RAG search for this workspace.
              </div>
            ) : (
              <div className="documents-list">
                {documents.map((doc, index) => (
                  <div key={index} className="document-item">
                    <div className="document-info">
                      <div className="document-title">{doc.title || 'Untitled'}</div>
                      {doc.source && <div className="document-source">Source: {doc.source}</div>}
                      {doc.chunk_count && (
                        <div className="document-meta">
                          {doc.chunk_count} chunk(s) • {doc.created_at && new Date(doc.created_at).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                    <button
                      className="delete-button"
                      onClick={() => handleDelete(doc.id)}
                      title="Delete document"
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
