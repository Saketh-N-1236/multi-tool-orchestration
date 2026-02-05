import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Code, Database, Search } from 'lucide-react';
import { chatAPI } from '../services/api';
import type { ChatResponse, ToolCall, ToolResult } from '../types/api';
import './ChatPage.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  tool_calls?: ToolCall[];
  tool_results?: ToolResult[];
  request_id?: string;
  metadata?: Record<string, any>;
  iterations?: number;
  session_id?: string;
}

interface ExecutionStage {
  stage: string;
  data: {
    message?: string;
    tools?: string[];
    tools_count?: number;
    error?: string;
    response?: string;
    tool_calls?: ToolCall[];
    tool_results?: ToolResult[];
    iterations?: number;
  };
  timestamp?: string;
}

const ChatPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [executionStage, setExecutionStage] = useState<ExecutionStage | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, executionStage]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    const userInput = input;
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setExecutionStage(null);

    // Start stream in parallel for execution stages (replaces "thinking" indicator)
    const streamAbortController = new AbortController();
    const streamPromise = fetch('/api/v1/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      signal: streamAbortController.signal,
      body: JSON.stringify({
        message: userInput,
        session_id: sessionId,
        max_iterations: 10,
        temperature: 0.7,
        max_tokens: 500,
      }),
    }).then(async (response) => {
      if (!response.ok) return;
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      if (reader) {
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data.trim() === '[DONE]') continue;

                try {
                  const stage: ExecutionStage = JSON.parse(data);
                  // Only update execution stage UI, don't use response
                  setExecutionStage(stage);
                } catch (e) {
                  if (!(e instanceof SyntaxError)) {
                    console.error('Error processing stage:', e);
                  }
                }
              }
            }
          }
        } catch (e: any) {
          // Stream was aborted or failed - that's okay
          if (e.name !== 'AbortError') {
            console.warn('Stream error:', e);
          }
        }
      }
    }).catch((e: any) => {
      // Ignore stream errors - it's just for UI feedback
      if (e.name !== 'AbortError') {
        console.warn('Stream failed:', e);
      }
    });

    // Main request: Use /chat endpoint (returns full response with metadata)
    try {
      const response = await chatAPI.sendMessage({
        message: userInput,
        session_id: sessionId,
        max_iterations: 10,
        temperature: 0.7,
        max_tokens: 500,
      });

      // Stop the stream once main request completes
      streamAbortController.abort();

      // Use response from /chat endpoint (has full metadata)
      const assistantMessage: Message = {
        id: `response-${Date.now()}`,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        tool_calls: response.tool_calls,
        tool_results: response.tool_results,
        request_id: response.request_id,
        session_id: response.session_id,
        metadata: response.metadata, // Full metadata from chat endpoint
        iterations: response.iterations,
      };
      
      setMessages((prev) => [...prev, assistantMessage]);
      
      // Update session ID if available
      if (response.session_id) {
        setSessionId(response.session_id);
      }

      // Clear execution stage
      setExecutionStage(null);
    } catch (error: any) {
      // Stop stream on error
      streamAbortController.abort();
      setExecutionStage(null);
      
      // Handle errors
      let errorContent = 'Failed to send message';
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        errorContent = 'Request timed out. The agent is taking too long to respond. Please try again with a simpler query or reduce max_iterations.';
      } else if (error.response?.status === 504) {
        errorContent = error.response?.data?.detail || 'Gateway timeout - agent execution took too long.';
      } else if (error.response?.data?.detail) {
        errorContent = error.response.data.detail;
      } else if (error.message) {
        errorContent = error.message;
      }
      
      const errorMessage: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Error: ${errorContent}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getToolIcon = (toolName: string) => {
    if (toolName.includes('sql')) return <Database size={16} />;
    if (toolName.includes('vector') || toolName.includes('search')) return <Search size={16} />;
    return <Code size={16} />;
  };

  const getStageLabel = (stage: string): string => {
    const labels: Record<string, string> = {
      initializing: 'Initializing...',
      agent_thinking: 'Thinking...',
      tool_executing: 'Executing tools...',
      tool_completed: 'Tools completed',
      finalizing: 'Finalizing...',
      completed: 'Completed',
      error: 'Error occurred',
    };
    return labels[stage] || 'Processing...';
  };

  return (
    <div className="chat-page">
      <div className="chat-container">
        <div className="chat-header">
          <h1>Chat Assistant</h1>
          <p>Ask questions and interact with the multi-tool orchestration system</p>
        </div>

        <div className="chat-content">
          <div className="messages-panel">
            <div className="messages-list">
              {messages.length === 0 ? (
                <div className="empty-state">
                  <h3>Start a conversation</h3>
                  <p>Send a message to begin chatting with the AI assistant</p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`message ${message.role}`}
                    onClick={() => setSelectedMessage(message)}
                  >
                    <div className="message-header">
                      <span className="message-role">{message.role === 'user' ? 'You' : 'Assistant'}</span>
                      <span className="message-time">
                        {message.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="message-content">{message.content}</div>
                    {message.tool_calls && message.tool_calls.length > 0 && (
                      <div className="tool-calls">
                        <div className="tool-calls-header">
                          Tools Used ({message.tool_calls.length})
                        </div>
                        {message.tool_calls.map((tool, idx) => (
                          <div key={idx} className="tool-call-item">
                            {getToolIcon(tool.tool_name)}
                            <span className="tool-name">{tool.tool_name}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
              {loading && executionStage && (
                <div className="message assistant execution-stage">
                  <div className="message-content">
                    <Loader2 className="spinner" size={20} />
                    <div className="stage-info">
                      <span className="stage-label">{getStageLabel(executionStage.stage)}</span>
                      {executionStage.data.message && (
                        <span className="stage-message">{executionStage.data.message}</span>
                      )}
                      {executionStage.data.tools && executionStage.data.tools.length > 0 && (
                        <div className="tools-list">
                          {executionStage.data.tools.map((tool, idx) => (
                            <span key={idx} className="tool-badge">
                              {getToolIcon(tool)}
                              {tool}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
              {loading && !executionStage && (
                <div className="message assistant">
                  <div className="message-content">
                    <Loader2 className="spinner" size={20} />
                    <span>Connecting...</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-container">
              <textarea
                className="chat-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message here..."
                rows={1}
              />
              <button
                className="send-button"
                onClick={handleSend}
                disabled={!input.trim() || loading}
              >
                {loading ? <Loader2 className="spinner" size={20} /> : <Send size={20} />}
              </button>
            </div>
          </div>

          {selectedMessage && (
            <div className="details-panel">
              <div className="details-header">
                <h2>Message Details</h2>
                <button className="close-button" onClick={() => setSelectedMessage(null)}>
                  ×
                </button>
              </div>
              <div className="details-content">
                <div className="detail-section">
                  <h3>Request ID</h3>
                  <p className="detail-value">{selectedMessage.request_id || selectedMessage.id}</p>
                </div>
                <div className="detail-section">
                  <h3>Timestamp</h3>
                  <p className="detail-value">
                    {selectedMessage.timestamp.toLocaleString()}
                  </p>
                </div>
                {selectedMessage.tool_calls && selectedMessage.tool_calls.length > 0 && (
                  <div className="detail-section">
                    <h3>Tool Calls</h3>
                    {selectedMessage.tool_calls.map((tool, idx) => (
                      <div key={idx} className="tool-detail">
                        <div className="tool-detail-header">
                          {getToolIcon(tool.tool_name)}
                          <span className="tool-detail-name">{tool.tool_name}</span>
                        </div>
                        <pre className="tool-detail-params">
                          {JSON.stringify(tool.params, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
                {selectedMessage.tool_results && selectedMessage.tool_results.length > 0 && (
                  <div className="detail-section">
                    <h3>Tool Results</h3>
                    {selectedMessage.tool_results.map((result, idx) => (
                      <div key={idx} className="tool-result">
                        <div className="tool-result-header">
                          {getToolIcon(result.tool_name)}
                          <span className="tool-result-name">{result.tool_name}</span>
                          {result.error ? (
                            <span className="tool-error">Error</span>
                          ) : (
                            <span className="tool-success">Success</span>
                          )}
                        </div>
                        {result.error ? (
                          <pre className="tool-result-error">{result.error}</pre>
                        ) : (
                          <pre className="tool-result-data">
                            {JSON.stringify(result.result, null, 2)}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {selectedMessage.metadata && Object.keys(selectedMessage.metadata).length > 0 && (
                  <div className="detail-section">
                    <h3>Metadata</h3>
                    <pre className="tool-detail-params">
                      {JSON.stringify(selectedMessage.metadata, null, 2)}
                    </pre>
                  </div>
                )}
                {selectedMessage.session_id && (
                  <div className="detail-section">
                    <h3>Session ID</h3>
                    <p className="detail-value">{selectedMessage.session_id}</p>
                  </div>
                )}
                {selectedMessage.iterations !== undefined && (
                  <div className="detail-section">
                    <h3>Iterations</h3>
                    <p className="detail-value">{selectedMessage.iterations}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
