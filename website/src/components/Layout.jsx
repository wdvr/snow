import { Outlet, Link } from 'react-router-dom'
import { FiGithub, FiHelpCircle, FiCoffee } from 'react-icons/fi'

function Layout() {
  return (
    <div className="layout">
      <header className="header">
        <div className="container">
          <Link to="/" className="logo">
            <span className="logo-icon">❄️</span>
            <span className="logo-text">Powder Chaser</span>
          </Link>
          <nav className="nav">
            <Link to="/support" className="nav-link">
              <FiHelpCircle /> Support
            </Link>
            <a
              href="https://github.com/wdvr/snow"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link"
            >
              <FiGithub /> GitHub
            </a>
            <a
              href="https://buymeacoffee.com/wdvr"
              target="_blank"
              rel="noopener noreferrer"
              className="nav-link"
            >
              <FiCoffee /> Support
            </a>
          </nav>
        </div>
      </header>

      <main className="main">
        <Outlet />
      </main>

      <footer className="footer">
        <div className="container">
          <div className="footer-content">
            <div className="footer-brand">
              <span className="logo-icon">❄️</span>
              <span>Powder Chaser</span>
            </div>
            <div className="footer-links">
              <Link to="/support">Support</Link>
              <a
                href="https://github.com/wdvr/snow"
                target="_blank"
                rel="noopener noreferrer"
              >
                GitHub
              </a>
              <a
                href="https://buymeacoffee.com/wdvr"
                target="_blank"
                rel="noopener noreferrer"
              >
                Buy Me a Coffee
              </a>
            </div>
            <div className="footer-copyright">
              &copy; {new Date().getFullYear()} Powder Chaser. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default Layout
