import './Header.css';

const Header = () => {

  return (
    <header className="app-header">
      <div className="header-left">
        <img src="/company_logo.png" alt="Company Logo" className="company-logo" />
      </div>
      <div className="header-center">
        <h2 className="app-title">Multi-Tool Orchestration</h2>
      </div>
      {/* User profile removed - no sign-in/sign-up functionality */}
    </header>
  );
};

export default Header;
