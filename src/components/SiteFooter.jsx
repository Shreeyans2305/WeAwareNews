export default function SiteFooter({ onNavigate, current }) {
  const links = [
    { id: 'feed', label: 'Feed' },
    { id: 'newsletters', label: 'Newsletters' },
    { id: 'podcasts', label: 'Podcasts' },
    { id: 'about', label: 'About' },
  ]

  return (
    <footer className="border-t border-white/10 px-6 py-10 md:px-12">
      <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <img src="/weaware-logo.png" alt="WeAware" className="h-8 w-auto" />
          <p className="text-xs text-white/35">
            Unbiased news, by design. Every story links back to its sources.
          </p>
        </div>
        <nav aria-label="Footer" className="perspective-stage flex flex-wrap items-center gap-1">
          {links.map((link) => (
            <button
              key={link.id}
              type="button"
              onClick={() => onNavigate(link.id)}
              aria-current={current === link.id ? 'page' : undefined}
              className={`nav-3d rounded-full px-5 py-1.5 text-[15px] transition-colors ${
                current === link.id
                  ? 'text-white underline underline-offset-4'
                  : 'text-white/50 hover:bg-white/10 hover:text-white'
              }`}
              style={current === link.id ? { textDecorationColor: '#00F0FF' } : undefined}
            >
              {link.label}
            </button>
          ))}
        </nav>
      </div>
      <p className="mt-6 text-xs text-white/35">© 2026 WeAware. All outlets and events in previews are fictional demos.</p>
    </footer>
  )
}
