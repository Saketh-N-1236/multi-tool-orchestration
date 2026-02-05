import { ReactNode } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';
import './MainLayout.css';

interface MainLayoutProps {
  children: ReactNode;
}

const MainLayout = ({ children }: MainLayoutProps) => {
  return (
    <div className="app-container">
      <Header />
      <div className="app-body">
        <Sidebar />
        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
