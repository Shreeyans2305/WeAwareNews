import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CheckCircle, Globe, Zap, Shield, FileText, Radio, ChevronRight, ArrowUpRight, Search, Bookmark, Share2 } from "lucide-react";

type Phase = "intro" | "reveal" | "home";

// ─── Fonts ────────────────────────────────────────────────────────────────────
const SERIF = "'Playfair Display', Georgia, serif";
const SANS  = "'Inter', system-ui, sans-serif";
const MONO  = "'DM Mono', 'Courier New', monospace";

// ─── Intro frames ─────────────────────────────────────────────────────────────
const FRAMES = [
  {
    category: "Climate",
    headline: "Arctic Ice Sheets Hit Record Low For Third Consecutive Year",
    image: "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Geopolitics",
    headline: "Emergency Summit Fails as Border Tensions Escalate in Three Regions",
    image: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Technology",
    headline: "Quantum Breakthrough Threatens Global Encryption Infrastructure",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Economy",
    headline: "Central Banks Signal Coordinated Rate Pause Through 2026",
    image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Science",
    headline: "Webb Telescope Detects Biosignature Candidates on Exoplanet K2-18b",
    image: "https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Health",
    headline: "WHO Mobilises Rapid Response as Novel Pathogen Spreads to Six Countries",
    image: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "AI",
    headline: "Internal Documents Reveal AGI Timeline Ahead of All Public Projections",
    image: "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=1920&h=1080&fit=crop&auto=format",
  },
  {
    category: "Conflict",
    headline: "Ceasefire Agreement Signed After 72 Hours of Intensive Mediation",
    image: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1920&h=1080&fit=crop&auto=format",
  },
];

// ─── News data ────────────────────────────────────────────────────────────────
const NAV_CATS = ["World", "Politics", "Technology", "Business", "Science", "Health", "Culture"];

const PIPELINE = [
  { Icon: Globe,    label: "Data Gathering" },
  { Icon: Shield,   label: "Fact Checking" },
  { Icon: Zap,      label: "Bias Removal" },
  { Icon: FileText, label: "Report Generation" },
  { Icon: Radio,    label: "Published" },
];

const FEATURED = {
  category: "World",
  headline: "Global AI Governance Framework Reaches Critical Juncture as Nations Divide on Oversight",
  excerpt: "A coalition of 47 nations struggled to agree on binding regulations for autonomous AI systems this week, exposing deep fault lines between those demanding strict controls and those prioritising unrestricted development. WeAware's analysis draws from 214 verified reports across six continents — no editorial position applied.",
  image: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=1400&h=900&fit=crop&auto=format",
  author: "WeAware AI",
  date: "July 21, 2026",
  readTime: "6 min read",
  sources: 214,
  neutrality: 98,
};

const SECONDARY = [
  {
    category: "Technology",
    headline: "Quantum Computing Breakthrough Forces Urgent Review of Global Financial Security",
    author: "WeAware AI",
    date: "July 21, 2026",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=400&fit=crop&auto=format",
    sources: 87,
    neutrality: 99,
  },
  {
    category: "Climate",
    headline: "Antarctic Mass Loss Accelerates to 340 Gigatons Per Year, Six Agencies Confirm",
    author: "WeAware AI",
    date: "July 21, 2026",
    image: "https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=600&h=400&fit=crop&auto=format",
    sources: 52,
    neutrality: 97,
  },
  {
    category: "Business",
    headline: "Chipmaker Alliance Announces $800B Plan to End Global AI Compute Bottleneck",
    author: "WeAware AI",
    date: "July 20, 2026",
    image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&h=400&fit=crop&auto=format",
    sources: 118,
    neutrality: 96,
  },
];

const BRIEFS = [
  { category: "Science",   text: "Webb telescope spectroscopic data shows dimethyl sulfide on K2-18b exceeding abiotic thresholds by factor of 12, reigniting life-detection debate." },
  { category: "Health",    text: "Genomic sequencing confirms novel betacoronavirus variant with R0 estimated 2.1–3.4. No evidence of severe disease in healthy adults as of publication." },
  { category: "Politics",  text: "Senate Intelligence Committee releases declassified 340-page report detailing AI-assisted influence operations during the 2025 election cycle." },
  { category: "Economy",   text: "Markets gained 4.2% following coordinated central bank statement — the broadest policy alignment among G20 members since 2009." },
  { category: "AI",        text: "Leaked internal timeline from leading AI lab suggests general capability threshold reached in 2025, one year ahead of any published roadmap." },
];

const OPINIONS = [
  { headline: "The Quiet Crisis in Long-Term Care Has Finally Reached Its Tipping Point", author: "Dr. Amara Diallo", role: "Health Policy Analyst", date: "July 21" },
  { headline: "Why AI Governance Has Become a Hollow Phrase in International Diplomacy",  author: "Theo Wakefield",   role: "Technology Correspondent", date: "July 20" },
  { headline: "Cities Are Repeating the Same Housing Mistakes From the 1970s, Again",      author: "Ruth Nakata",     role: "Urban Affairs Reporter",    date: "July 19" },
];

// ─── Intro Video ──────────────────────────────────────────────────────────────
function IntroVideo({ onComplete }: { onComplete: () => void }) {
  const [frameIdx, setFrameIdx] = useState(0);
  const [ending, setEnding] = useState(false);
  const ref = useRef(0);

  useEffect(() => {
    const id = setInterval(() => {
      ref.current += 1;
      if (ref.current >= FRAMES.length) {
        clearInterval(id);
        setEnding(true);
        setTimeout(onComplete, 800);
        return;
      }
      setFrameIdx(ref.current);
    }, 420);
    return () => clearInterval(id);
  }, [onComplete]);

  const frame = FRAMES[frameIdx];

  return (
    <motion.div
      className="fixed inset-0 overflow-hidden bg-black"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.6 }}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={frameIdx}
          className="absolute inset-0"
          initial={{ opacity: 0, scale: 1.05 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.1 }}
        >
          {/* Grayscale image */}
          <img
            src={frame.image}
            alt=""
            className="w-full h-full object-cover"
            style={{ filter: "grayscale(100%) contrast(1.1)" }}
          />
          {/* Overlay */}
          <div className="absolute inset-0"
            style={{ background: "linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.35) 55%, rgba(0,0,0,0.15) 100%)" }} />

          {/* Text */}
          <div className="absolute bottom-0 left-0 right-0 px-8 pb-20 md:px-16 md:pb-24 max-w-4xl">
            <motion.div
              initial={{ y: 12, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.14, delay: 0.05 }}
            >
              <span className="block mb-3 text-white/50 text-xs tracking-[0.25em] uppercase"
                style={{ fontFamily: MONO }}>
                {frame.category}
              </span>
              <h2 className="text-white font-bold leading-tight"
                style={{ fontFamily: SERIF, fontSize: "clamp(1.6rem, 3.5vw, 3rem)" }}>
                {frame.headline}
              </h2>
            </motion.div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Fade to black */}
      {ending && (
        <motion.div className="absolute inset-0 bg-black"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ duration: 0.65 }} />
      )}

      {/* Top bar */}
      <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-8 py-5 md:px-16">
        <span className="text-white font-bold text-sm tracking-tight" style={{ fontFamily: SERIF }}>
          WeAware
        </span>
        <button onClick={onComplete}
          className="text-white/40 text-xs tracking-widest uppercase hover:text-white transition-colors flex items-center gap-1"
          style={{ fontFamily: MONO }}>
          Skip <ChevronRight size={11} />
        </button>
      </div>

      {/* Progress */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1.5">
        {FRAMES.map((_, i) => (
          <div key={i} className="h-px transition-all duration-200"
            style={{ width: i === frameIdx ? 28 : 6, backgroundColor: i <= frameIdx ? "#fff" : "rgba(255,255,255,0.2)" }} />
        ))}
      </div>
    </motion.div>
  );
}

// ─── Reveal Screen ────────────────────────────────────────────────────────────
function RevealScreen({ onEnter }: { onEnter: () => void }) {
  return (
    <motion.div
      className="fixed inset-0 bg-black flex flex-col items-center justify-center overflow-hidden"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Hairline grid */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.04]"
        style={{
          backgroundImage: "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }} />

      <div className="text-center relative z-10 px-8">
        {/* Wordmark */}
        <motion.h1
          className="font-bold text-white"
          style={{ fontFamily: SERIF, fontSize: "clamp(3.5rem, 9vw, 7rem)", letterSpacing: "-0.02em" }}
          initial={{ opacity: 0, y: 28 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.25 }}
        >
          WeAware
        </motion.h1>

        {/* Rule */}
        <motion.div className="my-5 mx-auto border-t border-white/20"
          style={{ width: 120 }}
          initial={{ scaleX: 0 }} animate={{ scaleX: 1 }}
          transition={{ duration: 0.5, delay: 0.7 }} />

        {/* Tagline */}
        <motion.p
          className="text-white/40 text-xs tracking-[0.3em] uppercase"
          style={{ fontFamily: MONO }}
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.85 }}
        >
          Unbiased · Autonomous · Accurate
        </motion.p>

        {/* Pipeline */}
        <motion.div
          className="mt-10 flex flex-wrap items-center justify-center gap-y-2"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 1.1 }}
        >
          {PIPELINE.map(({ Icon, label }, i) => (
            <div key={label} className="flex items-center">
              <span className="text-white/30 text-xs flex items-center gap-1" style={{ fontFamily: MONO }}>
                <Icon size={10} />{label}
              </span>
              {i < PIPELINE.length - 1 && <span className="mx-2.5 text-white/15 text-xs">→</span>}
            </div>
          ))}
        </motion.div>

        {/* CTA */}
        <motion.button
          onClick={onEnter}
          className="mt-12 px-8 py-3 text-xs text-black font-semibold tracking-widest uppercase bg-white flex items-center gap-2 mx-auto hover:bg-white/90 transition-colors"
          style={{ fontFamily: MONO }}
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 1.45 }}
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
        >
          Enter WeAware <ArrowUpRight size={13} />
        </motion.button>
      </div>
    </motion.div>
  );
}

// ─── Home Page ────────────────────────────────────────────────────────────────
function HomePage() {
  const [activeNav, setActiveNav] = useState("World");

  return (
    <motion.div
      className="min-h-screen bg-background text-foreground"
      style={{ fontFamily: SANS }}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      transition={{ duration: 0.45 }}
    >
      {/* ── Top bar ── */}
      <div className="border-b border-border">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground tracking-widest uppercase" style={{ fontFamily: MONO }}>
            Monday, July 21, 2026
          </span>
          <div className="hidden md:flex items-center gap-4 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
            {PIPELINE.map(({ Icon, label }, i) => (
              <span key={label} className="flex items-center gap-1">
                {i < PIPELINE.length - 1
                  ? <span className="text-muted-foreground/50">{label}</span>
                  : <span className="flex items-center gap-1"><CheckCircle size={9} className="text-foreground" />{label}</span>
                }
              </span>
            ))}
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
            <span>214 sources verified</span>
            <span>Subscribe</span>
          </div>
        </div>
      </div>

      {/* ── Masthead ── */}
      <header className="border-b-2 border-foreground">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-7 text-center">
          <h1 className="font-bold tracking-tight leading-none"
            style={{ fontFamily: SERIF, fontSize: "clamp(2.8rem, 7vw, 5.5rem)", letterSpacing: "-0.02em" }}>
            WeAware
          </h1>
          <p className="mt-2 text-xs text-muted-foreground tracking-[0.28em] uppercase" style={{ fontFamily: MONO }}>
            Autonomous · Unbiased · AI-Verified News
          </p>
        </div>

        {/* Nav */}
        <nav className="border-t border-border">
          <div className="max-w-7xl mx-auto px-5 md:px-8 flex items-center justify-between">
            <ul className="flex items-center overflow-x-auto">
              {NAV_CATS.map(cat => (
                <li key={cat}>
                  <button
                    onClick={() => setActiveNav(cat)}
                    className={`px-4 py-3 text-xs tracking-widest uppercase whitespace-nowrap transition-colors ${
                      activeNav === cat
                        ? "text-foreground border-b-2 border-foreground font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                    style={{ fontFamily: MONO }}
                  >
                    {cat}
                  </button>
                </li>
              ))}
            </ul>
            <button className="p-2 text-muted-foreground hover:text-foreground transition-colors flex-shrink-0">
              <Search size={15} />
            </button>
          </div>
        </nav>
      </header>

      <main className="max-w-7xl mx-auto px-5 md:px-8 py-10">

        {/* ── Feature + Secondary ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 border border-border">

          {/* Feature */}
          <article className="lg:col-span-7 border-b lg:border-b-0 lg:border-r border-border cursor-pointer group">
            <div className="h-72 md:h-96 bg-muted overflow-hidden">
              <img
                src={FEATURED.image}
                alt={FEATURED.headline}
                className="w-full h-full object-cover grayscale opacity-90 group-hover:opacity-100 transition-opacity duration-500"
              />
            </div>
            <div className="p-7 md:p-9">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-xs tracking-widest uppercase text-foreground font-semibold border-b border-foreground pb-0.5"
                  style={{ fontFamily: MONO }}>
                  {FEATURED.category}
                </span>
                <span className="text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                  Featured Report
                </span>
              </div>
              <h2 className="font-bold leading-tight mb-4"
                style={{ fontFamily: SERIF, fontSize: "clamp(1.5rem, 2.5vw, 2.1rem)" }}>
                {FEATURED.headline}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground mb-6">
                {FEATURED.excerpt}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                  <span>{FEATURED.author}</span>
                  <span>·</span>
                  <span>{FEATURED.date}</span>
                  <span>·</span>
                  <span>{FEATURED.readTime}</span>
                  <span>·</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle size={10} />{FEATURED.sources} sources
                  </span>
                </div>
              </div>
            </div>
          </article>

          {/* Secondary */}
          <div className="lg:col-span-5 flex flex-col divide-y divide-border">
            {SECONDARY.map(story => (
              <article key={story.headline} className="flex gap-0 group cursor-pointer hover:bg-secondary transition-colors">
                <div className="flex-1 p-5">
                  <span className="text-xs tracking-widest uppercase font-semibold text-foreground border-b border-foreground pb-0.5 inline-block mb-2"
                    style={{ fontFamily: MONO }}>
                    {story.category}
                  </span>
                  <h3 className="font-semibold leading-snug text-sm md:text-base group-hover:underline underline-offset-2"
                    style={{ fontFamily: SERIF }}>
                    {story.headline}
                  </h3>
                  <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                    <span>{story.date}</span>
                    <span>·</span>
                    <span className="flex items-center gap-1"><CheckCircle size={9} />{story.sources} sources</span>
                  </div>
                </div>
                <div className="w-24 md:w-28 flex-shrink-0 overflow-hidden bg-muted">
                  <img
                    src={story.image}
                    alt={story.headline}
                    className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 transition-opacity duration-300"
                  />
                </div>
              </article>
            ))}
          </div>
        </div>

        {/* ── Section rule ── */}
        <div className="my-10 border-t-2 border-foreground" />

        {/* ── Briefs + Opinion ── */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">

          {/* In Brief */}
          <section className="lg:col-span-4">
            <h2 className="text-xs font-semibold tracking-[0.3em] uppercase mb-6 pb-3 border-b border-border"
              style={{ fontFamily: MONO }}>
              In Brief
            </h2>
            <div className="flex flex-col divide-y divide-border">
              {BRIEFS.map(brief => (
                <div key={brief.text} className="py-4 cursor-pointer group">
                  <span className="text-xs tracking-widest uppercase font-semibold text-foreground border-b border-foreground pb-0.5 inline-block mb-2"
                    style={{ fontFamily: MONO }}>
                    {brief.category}
                  </span>
                  <p className="text-sm leading-relaxed text-muted-foreground group-hover:text-foreground transition-colors">
                    {brief.text}
                  </p>
                </div>
              ))}
            </div>
          </section>

          {/* Opinion */}
          <section className="lg:col-span-4">
            <h2 className="text-xs font-semibold tracking-[0.3em] uppercase mb-6 pb-3 border-b border-border"
              style={{ fontFamily: MONO }}>
              Analysis
            </h2>
            <div className="flex flex-col divide-y divide-border">
              {OPINIONS.map((piece, i) => (
                <article key={piece.headline} className="py-5 group cursor-pointer">
                  <div className="flex items-start gap-4">
                    <span className="text-2xl font-bold text-muted-foreground/30 leading-none mt-0.5 select-none"
                      style={{ fontFamily: SERIF }}>
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="font-semibold leading-snug text-sm md:text-base group-hover:underline underline-offset-2"
                        style={{ fontFamily: SERIF }}>
                        {piece.headline}
                      </h3>
                      <div className="mt-2 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                        {piece.author} — {piece.role} · {piece.date}
                      </div>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </section>

          {/* Pipeline + Stats */}
          <aside className="lg:col-span-4">
            <h2 className="text-xs font-semibold tracking-[0.3em] uppercase mb-6 pb-3 border-b border-border"
              style={{ fontFamily: MONO }}>
              AI Pipeline
            </h2>

            {/* Pipeline stages */}
            <div className="flex flex-col gap-3 mb-8">
              {PIPELINE.map(({ Icon, label }, i) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs" style={{ fontFamily: MONO }}>
                    <Icon size={12} className="text-muted-foreground" />
                    <span className={i === PIPELINE.length - 1 ? "text-foreground font-semibold" : "text-muted-foreground"}>
                      {label}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-px bg-muted-foreground/20 relative">
                      <div className="absolute left-0 top-0 h-full bg-foreground" style={{ width: "100%" }} />
                    </div>
                    <CheckCircle size={11} className="text-foreground" />
                  </div>
                </div>
              ))}
            </div>

            {/* Stats grid */}
            <div className="border border-border p-5 grid grid-cols-2 gap-5">
              {[
                { label: "Reports Today", value: "847" },
                { label: "Sources Active", value: "12.4K" },
                { label: "Bias Removed", value: "2,341" },
                { label: "Avg. Neutrality", value: "97.8%" },
              ].map(({ label, value }) => (
                <div key={label}>
                  <div className="text-2xl font-bold leading-none" style={{ fontFamily: SERIF }}>{value}</div>
                  <div className="text-xs text-muted-foreground mt-1" style={{ fontFamily: MONO }}>{label}</div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="border-t-2 border-foreground mt-12">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-8 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <span className="text-xl font-bold" style={{ fontFamily: SERIF }}>WeAware</span>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
            {["About", "How It Works", "Transparency Report", "API", "Contact"].map(item => (
              <span key={item} className="hover:text-foreground cursor-pointer transition-colors tracking-wider">{item}</span>
            ))}
          </div>
          <span className="text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
            © 2026 WeAware — No editors. No bias.
          </span>
        </div>
      </footer>
    </motion.div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [phase, setPhase] = useState<Phase>("reveal");
  return (
    <div>
      <AnimatePresence mode="wait">
        {phase === "intro"  && <IntroVideo   key="intro"  onComplete={() => setPhase("reveal")} />}
        {phase === "reveal" && <RevealScreen key="reveal" onEnter={() => setPhase("home")} />}
        {phase === "home"   && <HomePage     key="home" />}
      </AnimatePresence>
    </div>
  );
}
