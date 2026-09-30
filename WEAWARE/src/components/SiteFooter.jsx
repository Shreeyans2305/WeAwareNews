export default function SiteFooter({ onNavigate, current }) {
  const links = [
    { id: 'feed', label: 'Feed' },
    { id: 'newsletters', label: 'Newsletters' },
    { id: 'podcasts', label: 'Podcasts' },
    { id: 'about', label: 'About' },
  ]

  return (
    <footer className="t-bg t-border border-t px-6 py-10 md:px-12">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2.5">
          <img src="/weaware-logo.png" alt="WeAware" className="h-6 w-auto" />
          <span className="font-display text-sm font-bold tracking-tight">WeAware</span>
          <span className="t-faint text-xs">— unbiased news, by design.</span>
        </div>
        <nav aria-label="Footer" className="flex flex-wrap items-center gap-5">
          {links.map((link) => (
            <button
              key={link.id}
              type="button"
              onClick={() => onNavigate(link.id)}
              aria-current={current === link.id ? 'page' : undefined}
              data-active={current === link.id}
              className="nav-link"
            >
              {link.label}
            </button>
          ))}
        </nav>
      </div>
      <p className="t-faint mx-auto mt-6 max-w-4xl text-xs">© 2026 WeAware. All outlets and events in previews are fictional demos.</p>
    </footer>
  )
}
