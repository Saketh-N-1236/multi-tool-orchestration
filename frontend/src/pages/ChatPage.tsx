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
}

const ChatPage = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [selectedMessage, setSelectedMessage] = useState<Message | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response: ChatResponse = await chatAPI.sendMessage({
        message: input,
        session_id: sessionId,
        max_iterations: 10,
        temperature: 0.7,
        max_tokens: 500,
      });

      const assistantMessage: Message = {
        id: response.request_id,
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        tool_calls: response.tool_calls,
        tool_results: response.tool_results,
        request_id: response.request_id,
      };

      setMessages((prev) => [...prev, assistantMessage]);
      if (response.session_id) {
        setSessionId(response.session_id);
      }
    } catch (error: any) {
      // Handle timeout errors specifically
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
              {loading && (
                <div className="message assistant">
                  <div className="message-content">
                    <Loader2 className="spinner" size={20} />
                    <span>Thinking...</span>
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
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatPage;
