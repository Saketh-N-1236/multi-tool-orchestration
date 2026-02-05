import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FileCode,
  Settings,
  FileText,
  Database,
  ChevronDown,
  ChevronRight,
  Table2,
} from 'lucide-react';
import './Sidebar.css';

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [projectOpen, setProjectOpen] = useState(false);

  const menuItems = [
    {
      id: 'overview',
      label: 'Overview',
      icon: LayoutDashboard,
      path: '/',
      active: location.pathname === '/' || location.pathname === '/chat',
    },
  ];

  const utilityItems = [
    {
      id: 'inference-logger',
      label: 'Inference Logger',
      icon: FileText,
      subtitle: 'Request & Response Logs',
      path: '/inference-logger',
      active: location.pathname === '/inference-logger',
    },
    {
      id: 'ml-logger',
      label: 'MLflow Logger',
      icon: Database,
      subtitle: 'Experiment Tracking',
      path: '/ml-logger',
      active: location.pathname === '/ml-logger',
    },
    {
      id: 'documents',
      label: 'Documents',
      icon: FileCode,
      subtitle: 'Document Management',
      path: '/documents',
      active: location.pathname === '/documents',
    },
    {
      id: 'tools',
      label: 'Tools',
      icon: Settings,
      subtitle: 'Tool Explorer',
      path: '/tools',
      active: location.pathname === '/tools',
    },
    {
      id: 'databases',
      label: 'Databases',
      icon: Table2,
      subtitle: 'Database Management',
      path: '/databases',
      active: location.pathname.startsWith('/databases'),
    },
  ];

  const handleNavigation = (path?: string) => {
    if (path) {
      navigate(path);
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-content">
        <div className="project-selector" onClick={() => setProjectOpen(!projectOpen)}>
          <span className="project-name">MULTI-TOOL ORCHESTRATION</span>
          {projectOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </div>

        <nav className="sidebar-nav">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`nav-item ${item.active ? 'active' : ''}`}
                onClick={() => handleNavigation(item.path)}
              >
                <Icon size={20} />
                <span>{item.label}</span>
              </button>
            );
          })}

          <div className="nav-section">
            {utilityItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  className={`nav-item ${item.active ? 'active' : ''}`}
                  onClick={() => handleNavigation(item.path)}
                >
                  <Icon size={20} />
                  <div className="nav-item-content">
                    <span className="nav-item-label">{item.label}</span>
                    {item.subtitle && <span className="nav-item-subtitle">{item.subtitle}</span>}
                  </div>
                </button>
              );
            })}
          </div>
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;
