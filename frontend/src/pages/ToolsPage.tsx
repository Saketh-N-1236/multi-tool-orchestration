import { useState, useEffect } from 'react';
import { Code, Server, CheckCircle, XCircle, Search } from 'lucide-react';
import { toolsAPI, healthAPI } from '../services/api';
import type { Tool } from '../types/api';
import './ToolsPage.css';

const ToolsPage = () => {
  const [tools, setTools] = useState<Tool[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [toolsResponse, healthResponse] = await Promise.all([
        toolsAPI.list(),
        healthAPI.check(),
      ]);
      setTools(toolsResponse.tools || []);
      setHealth(healthResponse);
    } catch (error: any) {
      console.error('Failed to load tools:', error);
      // Set empty states on error
      setTools([]);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      tool.server.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toolsByServer = filteredTools.reduce((acc, tool) => {
    if (!acc[tool.server]) {
      acc[tool.server] = [];
    }
    acc[tool.server].push(tool);
    return acc;
  }, {} as Record<string, Tool[]>);

  if (loading) {
    return (
      <div className="tools-page">
        <div className="loading-state">Loading tools...</div>
      </div>
    );
  }

  return (
    <div className="tools-page">
      <div className="tools-header">
        <div>
          <h1>Tools Explorer</h1>
          <p>Discover and explore available MCP tools</p>
        </div>
        {health && (
          <div className="health-status">
            <div className="health-item">
              <span className="health-label">LLM Provider:</span>
              <span className="health-value">{health.llm_provider}</span>
            </div>
            <div className="health-item">
              <span className="health-label">Status:</span>
              <span className={`health-value ${health.status === 'healthy' ? 'success' : 'error'}`}>
                {health.status}
              </span>
            </div>
          </div>
        )}
      </div>

      <div className="search-section">
        <div className="search-box">
          <Search size={18} />
          <input
            type="text"
            placeholder="Search tools by name, description, or server..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="tools-count">
          {filteredTools.length} tool{filteredTools.length !== 1 ? 's' : ''} found
        </div>
      </div>

      <div className="tools-content">
        {Object.keys(toolsByServer).length === 0 ? (
          <div className="empty-state">
            <Code size={48} />
            <h3>No tools found</h3>
            <p>No tools match your search criteria</p>
          </div>
        ) : (
          Object.entries(toolsByServer).map(([server, serverTools]) => (
            <div key={server} className="server-section">
              <div className="server-header">
                <Server size={20} />
                <h2>{server}</h2>
                <span className="tool-count">{serverTools.length} tools</span>
              </div>
              <div className="tools-grid">
                {serverTools.map((tool, idx) => (
                  <div key={idx} className="tool-card">
                    <div className="tool-card-header">
                      <Code size={20} />
                      <div className="tool-name">{tool.name}</div>
                      <div className="tool-version">v{tool.version}</div>
                    </div>
                    <div className="tool-description">{tool.description}</div>
                    
                    {/* Parameters Section */}
                    {tool.parameters && tool.parameters.length > 0 && (
                      <div className="tool-section">
                        <div className="tool-section-title">
                          <span>Parameters</span>
                        </div>
                        <div className="tool-parameters">
                          {tool.parameters.map((param, pIdx) => (
                            <div key={pIdx} className="tool-parameter">
                              <div className="parameter-header">
                                <span className="parameter-name">{param.name}</span>
                                <span className={`parameter-badge ${param.required ? 'required' : 'optional'}`}>
                                  {param.required ? 'Required' : 'Optional'}
                                </span>
                                <span className="parameter-type">{param.type}</span>
                              </div>
                              {param.description && (
                                <div className="parameter-description">{param.description}</div>
                              )}
                              {param.default !== undefined && (
                                <div className="parameter-default">Default: {JSON.stringify(param.default)}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {/* Expected Output Section */}
                    {tool.expected_output && (
                      <div className="tool-section">
                        <div className="tool-section-title">
                          <span>Expected Output</span>
                        </div>
                        <div className="tool-output">
                          <div className="output-type">Type: <code>{tool.expected_output.type}</code></div>
                          {tool.expected_output.description && (
                            <div className="output-description">{tool.expected_output.description}</div>
                          )}
                        </div>
                      </div>
                    )}
                    
                    <div className="tool-footer">
                      <div className="tool-server">
                        <Server size={14} />
                        <span>{tool.server}</span>
                      </div>
                      <div className="tool-status">
                        <CheckCircle size={14} className="status-icon success" />
                        <span>Available</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {health?.mcp_servers && (
        <div className="servers-section">
          <h2>MCP Servers</h2>
          <div className="servers-grid">
            {Object.entries(health.mcp_servers).map(([name, url]) => (
              <div key={name} className="server-card">
                <Server size={24} />
                <h3>{name}</h3>
                <p>{url as string}</p>
                <div className="server-status">
                  <CheckCircle size={16} className="status-icon success" />
                  <span>Connected</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolsPage;
