import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { CheckCircle, Globe, Zap, Shield, FileText, Radio, ChevronRight, ArrowUpRight, Search, Bookmark, Share2, ArrowLeft, Check } from "lucide-react";
import { HashRouter, Routes, Route, useNavigate, useParams } from "react-router";
import { ImageWithFallback } from "./components/figma/ImageWithFallback";
import LoginPage from "./components/LoginPage";


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
const NAV_CATS = ["World", "Politics", "Technology", "Business", "Science", "Health", "Climate", "Analysis"];

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
  { category: "Science",   text: "Webb telescope spectroscopic data shows dimethyl sulfide on K2-18b exceeding abiotic thresholds by factor of 12, reigniting life-detection debate.", image: "https://images.unsplash.com/photo-1446776653964-20c1d3a81b06?w=600&h=400&fit=crop&auto=format" },
  { category: "Health",    text: "Genomic sequencing confirms novel betacoronavirus variant with R0 estimated 2.1–3.4. No evidence of severe disease in healthy adults as of publication.", image: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&h=400&fit=crop&auto=format" },
  { category: "Politics",  text: "Senate Intelligence Committee releases declassified 340-page report detailing AI-assisted influence operations during the 2025 election cycle.", image: "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=600&h=400&fit=crop&auto=format" },
  { category: "Economy",   text: "Markets gained 4.2% following coordinated central bank statement — the broadest policy alignment among G20 members since 2009.", image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=600&h=400&fit=crop&auto=format" },
  { category: "AI",        text: "Leaked internal timeline from leading AI lab suggests general capability threshold reached in 2025, one year ahead of any published roadmap.", image: "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=600&h=400&fit=crop&auto=format" },
];

const OPINIONS = [
  { headline: "The Quiet Crisis in Long-Term Care Has Finally Reached Its Tipping Point", author: "Dr. Amara Diallo", role: "Health Policy Analyst", date: "July 21", image: "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=600&h=400&fit=crop&auto=format" },
  { headline: "Why AI Governance Has Become a Hollow Phrase in International Diplomacy",  author: "Theo Wakefield",   role: "Technology Correspondent", date: "July 20", image: "https://images.unsplash.com/photo-1677442135703-1787eea5ce01?w=600&h=400&fit=crop&auto=format" },
  { headline: "Cities Are Repeating the Same Housing Mistakes From the 1970s, Again",      author: "Ruth Nakata",     role: "Urban Affairs Reporter",    date: "July 19", image: "https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=600&h=400&fit=crop&auto=format" },
];

const slugify = (text: string) =>
  text.toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)+/g, '');

export interface Article {
  category: string;
  headline: string;
  excerpt?: string;
  image?: string;
  author: string;
  date: string;
  readTime?: string;
  sources: number;
  neutrality: number;
  type: string;
  role?: string;
}

const ALL_ARTICLES: Article[] = [
  { ...FEATURED, type: "featured" },
  ...SECONDARY.map(s => ({ ...s, type: "secondary" })),
  ...BRIEFS.map(b => ({
    category: b.category,
    headline: b.text,
    excerpt: b.text,
    image: b.image,
    author: "WeAware AI",
    date: "July 21, 2026",
    sources: 42,
    neutrality: 97,
    type: "brief"
  })),
  ...OPINIONS.map(o => ({
    category: "Analysis",
    headline: o.headline,
    excerpt: o.headline,
    image: o.image,
    author: o.author,
    role: o.role,
    date: o.date,
    sources: 18,
    neutrality: 98,
    type: "opinion"
  }))
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
          <ImageWithFallback
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
  const [userSession, setUserSession] = useState("");
  const [userRole, setUserRole] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    setUserSession(sessionStorage.getItem("weaware_user") || "");
    setUserRole(sessionStorage.getItem("weaware_role") || "");
  }, []);

  const handleSignOut = () => {
    sessionStorage.removeItem("weaware_auth");
    sessionStorage.removeItem("weaware_user");
    sessionStorage.removeItem("weaware_role");
    navigate("/");
  };

  const handleSelect = (story: any) => {
    const title = story.headline || story.text;
    navigate("/article/" + slugify(title));
  };

  // Filter all articles matching the active navigation tab
  const categoryArticles = ALL_ARTICLES.filter(
    (art) => art.category.toLowerCase() === activeNav.toLowerCase()
  );

  // Dynamically configure featured story for selected category (fallback to global FEATURED if empty)
  const featuredStory = categoryArticles[0] || { ...FEATURED, type: "featured" };

  // Select secondary stories excluding the currently featured story
  const remainingCategoryArticles = categoryArticles.filter(a => a.headline !== featuredStory.headline);
  const secondaryStories = remainingCategoryArticles.length > 0
    ? remainingCategoryArticles.slice(0, 3)
    : SECONDARY.filter(a => a.headline !== featuredStory.headline).slice(0, 3);

  // Select brief stories excluding stories already shown in featured or secondary
  const shownHeadlines = new Set([featuredStory.headline, ...secondaryStories.map(s => s.headline)]);
  const remainingBriefs = ALL_ARTICLES.filter(a => !shownHeadlines.has(a.headline) && a.category.toLowerCase() === activeNav.toLowerCase());
  const briefStories = remainingBriefs.length > 0
    ? remainingBriefs.slice(0, 5)
    : ALL_ARTICLES.filter(a => !shownHeadlines.has(a.headline) && a.type === "brief").slice(0, 5);

  // Select opinion/analysis stories excluding stories already shown
  const remainingOpinions = ALL_ARTICLES.filter(a => !shownHeadlines.has(a.headline) && a.type === "opinion");
  const opinionStories = remainingOpinions.slice(0, 3);

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
            {userSession ? (
              <div className="flex items-center gap-2">
                <span className="text-foreground border border-foreground/20 px-1.5 py-0.5 text-[10px] bg-secondary font-semibold">
                  {userSession.includes("@") ? userSession.split("@")[0] : userSession}: {userRole}
                </span>
                <button 
                  onClick={handleSignOut}
                  className="hover:text-foreground hover:underline cursor-pointer bg-transparent border-none p-0 text-[10px] font-mono tracking-widest font-semibold uppercase text-muted-foreground"
                >
                  [ Sign Out ]
                </button>
              </div>
            ) : (
              <span>Subscribe</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Masthead ── */}
      <header className="border-b-2 border-foreground">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-4 text-center">
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
          <article onClick={() => handleSelect(featuredStory)} className="lg:col-span-7 border-b lg:border-b-0 lg:border-r border-border cursor-pointer group">
            <div 
              className="aspect-[16/10] md:aspect-[16/9] w-full bg-muted overflow-hidden"
              style={{ maxHeight: "280px" }}
            >
              <ImageWithFallback
                src={featuredStory.image}
                alt={featuredStory.headline}
                className="w-full h-full object-cover grayscale opacity-90 group-hover:opacity-100 transition-opacity duration-500"
              />
            </div>
            <div className="p-7 md:p-9">
              <div className="flex items-center gap-3 mb-4">
                <span className="text-xs tracking-widest uppercase text-foreground font-semibold border-b border-foreground pb-0.5"
                  style={{ fontFamily: MONO }}>
                  {featuredStory.category}
                </span>
                <span className="text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                  Featured Report
                </span>
              </div>
              <h2 className="font-bold leading-tight mb-4"
                style={{ fontFamily: SERIF, fontSize: "clamp(1.5rem, 2.5vw, 2.1rem)" }}>
                {featuredStory.headline}
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground mb-6">
                {featuredStory.excerpt}
              </p>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
                  <span>{featuredStory.author}</span>
                  <span>·</span>
                  <span>{featuredStory.date}</span>
                  <span>·</span>
                  <span>{featuredStory.readTime || "5 min read"}</span>
                  <span>·</span>
                  <span className="flex items-center gap-1">
                    <CheckCircle size={10} />{featuredStory.sources} sources
                  </span>
                </div>
              </div>
            </div>
          </article>

          {/* Secondary */}
          <div className="lg:col-span-5 flex flex-col divide-y divide-border">
            {secondaryStories.map(story => (
              <article key={story.headline} onClick={() => handleSelect(story)} className="flex gap-0 group cursor-pointer hover:bg-secondary transition-colors">
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
                {story.image && (
                  <div className="w-24 md:w-28 flex-shrink-0 overflow-hidden bg-muted border-l border-border">
                    <ImageWithFallback
                      src={story.image}
                      alt={story.headline}
                      className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 transition-opacity duration-300"
                    />
                  </div>
                )}
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
              {briefStories.map(brief => (
                <div key={brief.headline} onClick={() => handleSelect(brief)} className="py-4 cursor-pointer group flex items-start gap-4 justify-between">
                  <div className="flex-1">
                    <span className="text-xs tracking-widest uppercase font-semibold text-foreground border-b border-foreground pb-0.5 inline-block mb-2"
                      style={{ fontFamily: MONO }}>
                      {brief.category}
                    </span>
                    <p className="text-sm leading-relaxed text-muted-foreground group-hover:text-foreground transition-colors">
                      {brief.headline}
                    </p>
                  </div>
                  {brief.image && (
                    <div className="w-16 h-16 md:w-20 md:h-20 flex-shrink-0 overflow-hidden bg-muted mt-2 border border-border">
                      <ImageWithFallback
                        src={brief.image}
                        alt={brief.category}
                        className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 transition-opacity duration-300"
                      />
                    </div>
                  )}
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
              {opinionStories.map((piece, i) => (
                <article key={piece.headline} onClick={() => handleSelect(piece)} className="py-5 group cursor-pointer">
                  <div className="flex items-start gap-4 justify-between">
                    <div className="flex items-start gap-4 flex-1">
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
                          {piece.author} {piece.role ? `— ${piece.role}` : ""} · {piece.date}
                        </div>
                      </div>
                    </div>
                    {piece.image && (
                      <div className="w-16 h-16 md:w-20 md:h-20 flex-shrink-0 overflow-hidden bg-muted border border-border">
                        <ImageWithFallback
                          src={piece.image}
                          alt={piece.headline}
                          className="w-full h-full object-cover grayscale opacity-80 group-hover:opacity-100 transition-opacity duration-300"
                        />
                      </div>
                    )}
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

function getArticleDetails(headline: string) {
  const defaultDetails = {
    paragraphs: [
      "The situation continues to unfold rapidly as international observers monitor developments. Preliminary assessments indicate a shifting consensus among key stakeholders, driven by technological adaptations and evolving regulatory frameworks.",
      "According to documents analyzed by WeAware AI across 48 distinct regional reports, the core of the issue lies in the alignment of compliance guidelines with operational realities. Industry representatives assert that excessive oversight could hinder progress, whereas public advocates emphasize the necessity of strict guardrails to prevent systemic risk.",
      "As of today, verification models indicate a 98% consensus match across verified public data repositories, with no signs of coordinated influence campaigns or localized bias anomalies."
    ],
    sourcesBreakdown: { government: 35, media: 45, academic: 20 },
    neutralityVectors: { left: 49, right: 51, bias: "Neutral" }
  };

  const articleDb: Record<string, typeof defaultDetails> = {
    "Global AI Governance Framework Reaches Critical Juncture as Nations Divide on Oversight": {
      paragraphs: [
        "In a landmark closed-door negotiation held in Geneva, delegates representing 47 nations failed to establish a unified regulatory charter for frontier artificial intelligence models. The primary deadlock remains the division between states advocating for pre-deployment licensing regimes—similar to pharmaceutical approvals—and those favoring a post-deployment liability model focused on demonstrable harms.",
        "The draft resolution, which aimed to establish a 'World AI Organization' (WAIO), was rejected after standard protocol definitions for 'autonomous reasoning' could not be resolved. Representatives from leading tech hubs argued that strict pre-licensing would stifle small-scale open-source developer communities, effectively solidifying a monopoly for existing tech conglomerates.",
        "WeAware's analysis of 214 regional source publications suggests that public sentiment remains highly polarized, yet factual reporting indicates that national cybersecurity agencies are quietly aligning on technical benchmark testing, regardless of the legislative impasse. This suggests a functional, standards-driven harmonization is occurring underneath the diplomatic friction."
      ],
      sourcesBreakdown: { government: 45, media: 30, academic: 25 },
      neutralityVectors: { left: 50, right: 50, bias: "Absolute Neutral" }
    },
    "Quantum Computing Breakthrough Forces Urgent Review of Global Financial Security": {
      paragraphs: [
        "A joint research consortium of physicists and cryptographers has successfully demonstrated a stable 2,000-qubit quantum processor capable of executing modular arithmetic computations at speeds previously considered theoretical. The breakthrough, which significantly reduces the decoherence window, brings the timeline for cracking standard RSA-2048 encryption keys closer by nearly half a decade.",
        "Global financial infrastructure, which relies heavily on public-key cryptography to secure transactions, communications, and ledger validations, is facing an immediate transition period. The National Institute of Standards and Technology (NIST) has issued an emergency advisory recommending accelerated adoption of post-quantum cryptographic (PQC) algorithms.",
        "According to 87 verified announcements from financial consortiums and security firms, the financial sector plans to allocate upward of $45 billion globally over the next 24 months to transition legacy public key systems. Analysts note that while the threat is real, the immediate risk is mitigated by the extreme scarcity and cost of manufacturing quantum processing units."
      ],
      sourcesBreakdown: { government: 30, media: 40, academic: 30 },
      neutralityVectors: { left: 48, right: 52, bias: "Factual" }
    },
    "Antarctic Mass Loss Accelerates to 340 Gigatons Per Year, Six Agencies Confirm": {
      paragraphs: [
        "A unified report blending satellite gravimetry, altimetry, and radar interferometry has confirmed that the Antarctic Ice Sheet is losing mass at an accelerated rate of approximately 340 gigatons per year. This rate represents a 22% increase in ice discharge compared to the previous decade, primarily driven by the warming of circumpolar deep water currents encroaching on ice shelf foundations.",
        "The collaborative analysis, which reconciled data from ESA's CryoSat-2, NASA's ICESat-2, and regional ground sensor arrays, highlights the Amundsen Sea Sector as the most critical point of vulnerability. Glaciologists warned that the destabilization of the Thwaites Glacier shelf could trigger a multi-foot sea-level rise over the next two centuries if oceanic thermal trends persist.",
        "Factual coverage across international research bodies displays a high level of consensus (97.8% neutrality). The report stresses that local mitigation is impossible, and global efforts must pivot toward monitoring coastal vulnerability zones to plan long-term infrastructure adaptation."
      ],
      sourcesBreakdown: { government: 55, media: 15, academic: 30 },
      neutralityVectors: { left: 50, right: 50, bias: "Absolute Factual" }
    },
    "Chipmaker Alliance Announces $800B Plan to End Global AI Compute Bottleneck": {
      paragraphs: [
        "A newly formed consortium of semiconductor manufacturers, hyperscalers, and sovereign wealth funds has announced an unprecedented $800 billion capital expenditure plan to establish a decentralized global chip fabrication network. The initiative aims to build ten advanced packaging and lithography facilities across Europe, North America, and Japan over the next six years.",
        "The announcement is a direct response to the ongoing compute supply bottleneck, which has restricted AI development to a handful of heavily capitalized entities. By diversifying fabrication sites away from geographically concentrated zones, the alliance seeks to stabilize supply chains against geopolitical disruptions.",
        "Industry analysts are optimistic but emphasize the acute shortage of specialized technicians and extreme ultraviolet (EUV) lithography systems. WeAware's cross-source validation confirmed that while construction on three sites will begin immediately, full operational capacity is not expected until late 2029."
      ],
      sourcesBreakdown: { government: 20, media: 60, academic: 20 },
      neutralityVectors: { left: 47, right: 53, bias: "Industry Consensus" }
    },
    "The Quiet Crisis in Long-Term Care Has Finally Reached Its Tipping Point": {
      paragraphs: [
        "Demographic realities are colliding with systemic underfunding in public healthcare systems as the first wave of the baby boomer generation enters their eighties. The deficit in long-term care beds, coupled with a severe shortage of certified nursing assistants, has created a silent emergency affecting millions of families globally.",
        "Healthcare policies have historically prioritized acute care hospitals, leaving home-care subsidies and long-term residential facilities underfunded. The situation is exacerbated by high turnover rates among care workers, who face low wages and strenuous working conditions.",
        "Analysts from the World Health Organization suggest that restructuring long-term care will require national social insurance programs to be redesigned. In the absence of major policy shifts, the burden of care will continue to fall disproportionately on unpaid family members, limiting economic productivity and worsening public health outcomes."
      ],
      sourcesBreakdown: { government: 40, media: 30, academic: 30 },
      neutralityVectors: { left: 52, right: 48, bias: "Policy Analytical" }
    },
    "Why AI Governance Has Become a Hollow Phrase in International Diplomacy": {
      paragraphs: [
        "As multinational forums repeatedly publish non-binding declarations on AI ethics, the gulf between diplomatic rhetoric and state practice continues to widen. While communiqués celebrate 'human-centric' designs, military and economic realities dictate a quiet arms race in computing infrastructure and model capacity.",
        "Strategic competition between major technological powers has made binding international treaties highly unlikely. Instead, AI governance is being weaponized as a tool of foreign policy, with states forming rival blocs to control export standards and compute resources.",
        "Factual analysis of international security papers indicates that standardizing AI verification protocols is the only practical pathway to prevent systemic risks. Without concrete verification mechanisms—similar to nuclear non-proliferation frameworks—ethical declarations will remain largely symbolic."
      ],
      sourcesBreakdown: { government: 50, media: 25, academic: 25 },
      neutralityVectors: { left: 49, right: 51, bias: "Geopolitical Realist" }
    },
    "Cities Are Repeating the Same Housing Mistakes From the 1970s, Again": {
      paragraphs: [
        "Municipal governments struggling with skyrocketing rents are increasingly turning back to rent stabilization and strict zoning regulations. However, historic data indicates these measures often suppress new construction, leading to long-term housing deficits that exacerbate the very affordability crises they were meant to solve.",
        "The root cause of urban housing shortages remains restrictive zoning laws that protect low-density neighborhoods close to transit hubs. While rent caps provide short-term relief to current tenants, they disincentivize private developers from building the dense, mixed-use housing units necessary to meet modern urban demand.",
        "Economists across both sides of the spectrum agree that housing supply elasticity is key to stabilizing urban living costs. Upzoning land, streamlining permit approvals, and providing targeted public housing subsidies represent the most viable path forward to sustainable housing security."
      ],
      sourcesBreakdown: { government: 35, media: 35, academic: 30 },
      neutralityVectors: { left: 48, right: 52, bias: "Economic Consensus" }
    }
  };

  return articleDb[headline] || defaultDetails;
}

function ArticlePage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const article = ALL_ARTICLES.find(a => slugify(a.headline) === slug) as any;

  useEffect(() => {
    if (!article) {
      navigate("/", { replace: true });
    }
  }, [article, navigate]);

  if (!article) {
    return null;
  }

  const details = getArticleDetails(article.headline);
  const [bookmarked, setBookmarked] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      className="min-h-screen bg-background text-foreground"
      style={{ fontFamily: SANS }}
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -15 }}
      transition={{ duration: 0.4 }}
    >
      {/* Top sticky navigation */}
      <div className="sticky top-0 z-50 bg-background/80 backdrop-blur-md border-b border-border">
        <div className="max-w-7xl mx-auto px-5 md:px-8 py-3 flex items-center justify-between">
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 text-xs tracking-wider uppercase text-muted-foreground hover:text-foreground transition-colors font-medium animate-pulse hover:animate-none"
            style={{ fontFamily: MONO }}
          >
            <ArrowLeft size={14} /> Back
          </button>
          
          <span 
            onClick={() => navigate("/")}
            className="text-xl font-bold cursor-pointer hover:opacity-85 transition-opacity" 
            style={{ fontFamily: SERIF }}
          >
            WeAware
          </span>

          <div className="flex items-center gap-3">
            <button 
              onClick={() => setBookmarked(!bookmarked)}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors"
              title="Bookmark Report"
            >
              <Bookmark size={15} className={bookmarked ? "fill-foreground text-foreground" : ""} />
            </button>
            <button 
              onClick={handleShare}
              className="p-2 text-muted-foreground hover:text-foreground transition-colors relative"
              title="Copy Link"
            >
              {copied ? <Check size={15} className="text-emerald-500 animate-bounce" /> : <Share2 size={15} />}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-5 md:px-8 py-10">
        {/* Article Category & Title */}
        <div className="max-w-4xl mb-8">
          <span 
            className="text-xs tracking-[0.2em] uppercase text-foreground font-semibold border-b-2 border-foreground pb-1"
            style={{ fontFamily: MONO }}
          >
            {article.category}
          </span>
          
          <h1 
            className="mt-6 font-bold leading-tight tracking-tight text-foreground"
            style={{ fontFamily: SERIF, fontSize: "clamp(2rem, 4vw, 3.2rem)" }}
          >
            {article.headline}
          </h1>

          <div className="mt-6 flex flex-wrap items-center gap-4 text-xs text-muted-foreground" style={{ fontFamily: MONO }}>
            <div>
              <span className="text-foreground font-semibold">{article.author}</span>
              {article.role && <span className="opacity-60"> — {article.role}</span>}
            </div>
            <span>•</span>
            <span>{article.date}</span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <CheckCircle size={12} className="text-foreground" /> {article.sources} Verified Sources
            </span>
          </div>
        </div>

        {/* Hero Image */}
        {article.image && (
          <div className="mb-10 aspect-[21/9] w-full bg-muted overflow-hidden border border-border">
            <ImageWithFallback
              src={article.image}
              alt={article.headline}
              className="w-full h-full object-cover grayscale opacity-90 hover:opacity-100 hover:grayscale-0 transition-all duration-700"
            />
          </div>
        )}

        {/* Content Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12">
          {/* Main Body Column */}
          <div className="lg:col-span-8 space-y-6">
            {details.paragraphs.map((p, idx) => (
              <p 
                key={idx} 
                className={`text-base md:text-lg leading-relaxed text-muted-foreground ${
                  idx === 0 ? "first-letter:text-5xl first-letter:font-bold first-letter:text-foreground first-letter:mr-3 first-letter:float-left first-letter:font-serif first-letter:leading-none" : ""
                }`}
                style={{ fontFamily: SANS }}
              >
                {p}
              </p>
            ))}

            <div className="pt-8 border-t border-border mt-8">
              <h3 className="text-xs tracking-widest uppercase font-semibold text-foreground mb-4" style={{ fontFamily: MONO }}>
                Factual Consensus Summary
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground italic bg-secondary p-5 border-l-4 border-foreground" style={{ fontFamily: SANS }}>
                "WeAware's autonomous ingestion system gathered {article.sources} separate source datasets. Cross-checking algorithms resolved factual claims with a {article.neutrality}% match index. No signs of opinionated embellishment or artificial narrative pacing were introduced in the generation of this brief."
              </p>
            </div>
          </div>

          {/* Verification Sidebar Column */}
          <div className="lg:col-span-4 space-y-6">
            <div className="border border-border p-6 bg-secondary/50 backdrop-blur-sm space-y-6 sticky top-24">
              <div>
                <h3 className="text-xs tracking-[0.15em] uppercase font-bold text-foreground mb-4 border-b border-border pb-2" style={{ fontFamily: MONO }}>
                  AI Audit Report
                </h3>
                
                {/* Neutrality Index gauge */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground" style={{ fontFamily: MONO }}>Neutrality Score</span>
                  <span className="text-sm font-bold text-foreground" style={{ fontFamily: MONO }}>{article.neutrality}%</span>
                </div>
                <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
                  <div className="h-full bg-foreground transition-all duration-1000" style={{ width: `${article.neutrality}%` }} />
                </div>
              </div>

              <div>
                <span className="text-[10px] tracking-widest uppercase text-muted-foreground block mb-2" style={{ fontFamily: MONO }}>
                  Source Distribution
                </span>
                <div className="space-y-2 text-xs" style={{ fontFamily: MONO }}>
                  <div className="flex justify-between">
                    <span>Govt. / Official Records</span>
                    <span className="font-semibold text-foreground">{details.sourcesBreakdown.government}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Independent Media</span>
                    <span className="font-semibold text-foreground">{details.sourcesBreakdown.media}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Academic / Research</span>
                    <span className="font-semibold text-foreground">{details.sourcesBreakdown.academic}%</span>
                  </div>
                </div>
              </div>

              <div className="border-t border-border pt-4">
                <span className="text-[10px] tracking-widest uppercase text-muted-foreground block mb-1" style={{ fontFamily: MONO }}>
                  Verified Bias Vector
                </span>
                <div className="flex items-center gap-2 justify-between">
                  <div className="text-sm font-bold text-foreground" style={{ fontFamily: SERIF }}>
                    {details.neutralityVectors.bias}
                  </div>
                  <span className="text-[10px] bg-foreground text-background px-1.5 py-0.5 rounded uppercase font-semibold" style={{ fontFamily: MONO }}>
                    Pass
                  </span>
                </div>
              </div>

              <div className="text-[10px] text-muted-foreground/60 leading-normal pt-2 border-t border-border/40" style={{ fontFamily: MONO }}>
                This report was verified autonomously using decentralized data consensus models. No editors or human intervention modified this analysis.
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function HomeRouteWrapper() {
  const navigate = useNavigate();
  const isAuth = sessionStorage.getItem("weaware_auth") === "true";

  const handleEnter = () => {
    navigate("/login");
  };

  return (
    <AnimatePresence mode="wait">
      {isAuth ? (
        <HomePage key="home" />
      ) : (
        <RevealScreen key="reveal" onEnter={handleEnter} />
      )}
    </AnimatePresence>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
function AuthGuard({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const auth = sessionStorage.getItem("weaware_auth");
    if (auth !== "true") {
      navigate("/login", { replace: true });
    } else {
      setAuthorized(true);
    }
  }, [navigate]);

  if (!authorized) return null;
  return <>{children}</>;
}

// ─── App ──────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<HomeRouteWrapper />} />
        <Route path="/article/:slug" element={<AuthGuard><ArticlePage /></AuthGuard>} />
      </Routes>
    </HashRouter>
  );
}
