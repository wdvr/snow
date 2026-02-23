import { Outlet, useLocation } from 'react-router-dom'
import { Header } from './Header'
import { Footer } from './Footer'

export function Layout() {
  const location = useLocation()
  const isChatPage = location.pathname.startsWith('/chat')

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className={`flex-1 ${isChatPage ? '' : 'pb-8'}`}>
        <Outlet />
      </main>
      {!isChatPage && <Footer />}
    </div>
  )
}
