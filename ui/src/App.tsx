import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Search from './pages/Search'
import Documents from './pages/Documents'
import DocumentDetail from './pages/DocumentDetail'
import FileBrowser from './pages/FileBrowser'
import Admin from './pages/Admin'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              {/* Logo */}
              <div className="flex items-center">
                <svg className="h-8 w-8 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <span className="ml-2 text-xl font-bold text-gray-900">LAN Search</span>
              </div>

              {/* Navigation */}
              <nav className="flex space-x-8">
                <NavLink
                  to="/"
                  className={({ isActive }) =>
                    `px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-primary-500 border-b-2 border-primary-500'
                        : 'text-gray-600 hover:text-gray-900'
                    }`
                  }
                >
                  Search
                </NavLink>
                <NavLink
                  to="/documents"
                  className={({ isActive }) =>
                    `px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-primary-500 border-b-2 border-primary-500'
                        : 'text-gray-600 hover:text-gray-900'
                    }`
                  }
                >
                  Documents
                </NavLink>
                <NavLink
                  to="/files"
                  className={({ isActive }) =>
                    `px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-primary-500 border-b-2 border-primary-500'
                        : 'text-gray-600 hover:text-gray-900'
                    }`
                  }
                >
                  Files
                </NavLink>
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-primary-500 border-b-2 border-primary-500'
                        : 'text-gray-600 hover:text-gray-900'
                    }`
                  }
                >
                  Admin
                </NavLink>
              </nav>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main>
          <Routes>
            <Route path="/" element={<Search />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/documents/:id" element={<DocumentDetail />} />
            <Route path="/files" element={<FileBrowser />} />
            <Route path="/admin" element={<Admin />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
