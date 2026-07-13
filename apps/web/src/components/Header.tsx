import { Link } from 'react-router-dom'

export default function Header() {
  return (
    <header className="bg-primary text-on-primary shadow-lg">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-on-primary rounded-md flex items-center justify-center font-bold text-primary">
              AI
            </div>
            <h1 className="text-h2 font-bold">SDLC Platform</h1>
          </Link>
          <nav className="flex gap-6">
            <Link to="/" className="hover:opacity-80 transition">Dashboard</Link>
            <Link to="/requirements" className="hover:opacity-80 transition">Requirements</Link>
            <Link to="/design" className="hover:opacity-80 transition">Design</Link>
            <Link to="/implementation" className="hover:opacity-80 transition">Implementation</Link>
            <Link to="/testing" className="hover:opacity-80 transition">Testing</Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
