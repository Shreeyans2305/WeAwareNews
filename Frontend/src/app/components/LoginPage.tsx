import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Shield, ArrowUpRight, Lock, User, Terminal } from "lucide-react";
import { useNavigate } from "react-router";
import { ImageWithFallback } from "./figma/ImageWithFallback";
import { supabase } from "../../lib/supabase";

// Fonts matching standard configuration
const SERIF = "'Playfair Display', Georgia, serif";
const SANS  = "'Inter', system-ui, sans-serif";
const MONO  = "'DM Mono', 'Courier New', monospace";

// Mock collateral data for halftone news collage
const COLLAGE_ITEMS = [
  {
    tag: "INGESTION ENGINE",
    title: "LEDGER INTEGRITY AUDIT REVEALS ZERO ANOMALIES ACROSS 1,200 SOURCES",
    img: "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&h=400&fit=crop&auto=format",
    sources: "412 nodes verified"
  },
  {
    tag: "BIAS ANALYSIS",
    title: "EDITORIAL NEUTRALITY VECTOR REMAINS AT STATIC 99.8% CONFIDENCE COEFFICIENT",
    img: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=600&h=400&fit=crop&auto=format",
    sources: "Ingress consensus pass"
  },
  {
    tag: "GLOBAL SYNAPSE",
    title: "DECENTRALIZED HARVESTING NETWORKS DEPLOY PROTOCOL 1.9 SECURING DATA FEEDS",
    img: "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=600&h=400&fit=crop&auto=format",
    sources: "TLS 1.3 encryption active"
  },
  {
    tag: "COGNITIVE OVERLAY",
    title: "SUBJECTIVE TERMINOLOGY REMOVAL RATE HITS 1.2M PHRASES PER SEC",
    img: "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&h=400&fit=crop&auto=format",
    sources: "Semantic scrub completed"
  }
];

const TICKER_LOGS = [
  "Ingesting 847 wire datasets...",
  "Running Zero-Knowledge consensus nodes...",
  "Applying semantic neutralization model 3.0...",
  "Scrubbing subjective adjectives...",
  "Validating network integrity vectors...",
  "Cryptographic ledger signature: [OK]",
  "Consensus reached on 214 data streams...",
  "Bilingual translation layers synchronized..."
];

// Design theme configuration (only keeping Muted Recycled variant)
const theme = {
  bg: "#DFDCD6",
  fg: "#030213",
  cardBg: "#D6D3CD",
  border: "rgba(0, 0, 0, 0.15)",
  mutedFg: "#5c5a54",
  accent: "#030213",
  accentFg: "#DFDCD6",
  paperGrain: true,
  japanese: false,
  gridStyle: "linear-gradient(rgba(0,0,0,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px)",
  name: "Muted Recycled"
};

export default function LoginPage() {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [tickerIndex, setTickerIndex] = useState(0);
  const [verificationIndex, setVerificationIndex] = useState(0);

  const navigate = useNavigate();

  // Rotate ticker logs
  useEffect(() => {
    const id = setInterval(() => {
      setTickerIndex(prev => (prev + 1) % TICKER_LOGS.length);
    }, 3500);
    return () => clearInterval(id);
  }, []);

  // Rotate verification items index for mockup verification animation at the bottom
  useEffect(() => {
    const id = setInterval(() => {
      setVerificationIndex(prev => (prev + 1) % 3);
    }, 4000);
    return () => clearInterval(id);
  }, []);

  /** Guest / anonymous access — no Supabase account needed */
  const handleSkip = () => {
    sessionStorage.setItem("weaware_auth", "true");
    sessionStorage.setItem("weaware_user", "Guest Reader");
    sessionStorage.setItem("weaware_role", "Anonymous Guest");
    navigate("/", { replace: true });
  };

  /** Sign in or sign up via Supabase */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setErrorMessage("Email and password are required.");
      return;
    }
    if (isSignUp && !fullName.trim()) {
      setErrorMessage("Full name is required to create an account.");
      return;
    }

    setErrorMessage("");
    setSuccessMessage("");
    setIsSubmitting(true);

    try {
      if (isSignUp) {
        // ── Sign Up ──────────────────────────────────────────
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: fullName } },
        });
        if (error) throw error;

        if (data.session) {
          // Auto-confirmed (e.g. email confirm disabled in Supabase dashboard)
          sessionStorage.setItem("weaware_auth", "true");
          sessionStorage.setItem("weaware_user", email);
          sessionStorage.setItem("weaware_role", data.user?.user_metadata?.role || "reader");
          navigate("/", { replace: true });
        } else {
          // Email confirmation required — tell the user
          setSuccessMessage(
            "Account created! Check your email and click the confirmation link, then sign in."
          );
          setIsSignUp(false);
        }
      } else {
        // ── Sign In ──────────────────────────────────────────
        const { data, error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;

        const profile = data.user?.user_metadata;
        sessionStorage.setItem("weaware_auth", "true");
        sessionStorage.setItem("weaware_user", data.user?.email ?? email);
        sessionStorage.setItem("weaware_role", profile?.role ?? "reader");
        navigate("/", { replace: true });
      }
    } catch (err: any) {
      setErrorMessage(err.message ?? "Authentication failed. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div
      animate={{ backgroundColor: theme.bg, color: theme.fg }}
      transition={{ duration: 0.4 }}
      className="min-h-screen relative flex overflow-hidden w-full select-none"
      style={{ fontFamily: SANS }}
    >
      {/* Dynamic broadsheet hairline grid lines */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-40 transition-all duration-300"
        style={{
          backgroundImage: theme.gridStyle,
          backgroundSize: "40px 40px"
        }} 
      />

      {/* SVG noise overlay for tactile paper realism */}
      {theme.paperGrain && (
        <div 
          className="absolute inset-0 pointer-events-none opacity-[0.03] mix-blend-overlay"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
          }}
        />
      )}

      {/* Responsive layout container */}
      <div className="flex w-full relative min-h-screen">
        
        {/* ================= LEFT SIDE: DIGI-BROADSHEET COLLAGE (Hidden on mobile/tablet) ================= */}
        <div className="hidden lg:flex w-[56%] flex-col relative p-12 justify-between border-r border-black/10 overflow-hidden">
          
          {/* Top Broadside Header */}
          <div className="relative z-10 flex items-center justify-between border-b border-black/15 pb-4">
            <div>
              <span className="font-mono text-xs tracking-[0.25em] font-semibold opacity-70">
                WEAWARE // EDITORIAL PROTOCOL
              </span>
            </div>
            <div className="flex items-center gap-3 text-xs font-mono opacity-80">
              <span className="animate-pulse flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-600 inline-block"></span>
                Consensus Secured
              </span>
              <span>•</span>
              <span>214 Node Validations</span>
            </div>
          </div>

          {/* Broadside Masthead (Large Title) */}
          <div className="my-6 relative z-10 text-center py-6 border-b-2 border-black/20">
            <h2 className="text-5xl font-extrabold tracking-tighter uppercase" style={{ fontFamily: SERIF, letterSpacing: "-0.04em" }}>
              THE DAILY PRESS
            </h2>
            <p className="mt-2 text-[10px] tracking-[0.3em] font-mono uppercase opacity-70">
              unbiased · autonomous · cryptographic integrity
            </p>
          </div>

          {/* news collage grid */}
          <div className="grid grid-cols-2 gap-6 relative z-10 my-auto">
            {COLLAGE_ITEMS.map((item, idx) => (
              <div 
                key={idx} 
                className="group border border-black/10 bg-white/20 backdrop-blur-sm p-4 relative overflow-hidden transition-all hover:bg-white/40"
                style={{ borderColor: theme.border }}
              >
                {/* Halftone image container */}
                <div className="relative aspect-[3/2] w-full bg-neutral-300 overflow-hidden border border-black/10 mb-3">
                  <ImageWithFallback 
                    src={item.img} 
                    alt={item.title} 
                    className="w-full h-full object-cover grayscale contrast-125 transition-all duration-500 group-hover:scale-105"
                  />
                  {/* Halftone dot-screen overlay */}
                  <div 
                    className="absolute inset-0 pointer-events-none opacity-45 mix-blend-multiply"
                    style={{
                      backgroundImage: "radial-gradient(circle, #000000 20%, transparent 22%)",
                      backgroundSize: "3px 3px"
                    }}
                  />
                </div>
                <div className="flex items-center justify-between text-[9px] font-mono opacity-70 mb-1">
                  <span>[{item.tag}]</span>
                  <span>{item.sources}</span>
                </div>
                <h3 className="text-xs font-semibold leading-tight tracking-tight uppercase" style={{ fontFamily: SANS }}>
                  {item.title}
                </h3>
              </div>
            ))}
          </div>

          {/* Live system state console at bottom */}
          <div className="relative z-10 border-t border-black/15 pt-4 mt-auto">
            <div className="flex items-center justify-between text-xs font-mono">
              <div className="flex items-center gap-2">
                <Terminal size={12} className="text-emerald-700 animate-pulse" />
                <span className="opacity-70">INTEGRITY_LOG:</span>
                <span className="text-emerald-800 font-semibold">{TICKER_LOGS[tickerIndex]}</span>
              </div>
              <span className="opacity-50 text-[10px]">Node hash: d6f882a...</span>
            </div>
          </div>

          {/* SVG sloped folding seam overlay */}
          <svg 
            className="absolute inset-y-0 right-[-1px] w-[50px] h-full pointer-events-none z-20" 
            preserveAspectRatio="none" 
            viewBox="0 0 100 100"
          >
            {/* Soft gradient shadow simulating a newspaper spine / folded sheet */}
            <path 
              d="M 100 0 L 70 100 L 98 100 L 100 0 Z" 
              fill="url(#seamShadow)"
              opacity="0.45"
            />
            {/* The razor-thin folded line seam */}
            <line 
              x1="100" y1="0" x2="70" y2="100" 
              stroke={theme.fg} 
              strokeWidth="0.5" 
              opacity="0.15"
            />
            <defs>
              <linearGradient id="seamShadow" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#030213" stopOpacity="0.4"/>
                <stop offset="70%" stopColor="#030213" stopOpacity="0.1"/>
                <stop offset="100%" stopColor="#030213" stopOpacity="0"/>
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* ================= RIGHT SIDE: DYNAMIC LOGIN FORM PANEL ================= */}
        <div className="flex-1 flex flex-col justify-between p-8 md:p-12 relative overflow-hidden bg-white/10">
          
          {/* Top navigation/Masthead for small screens */}
          <div className="flex items-center justify-between lg:justify-end">
            <div className="lg:hidden">
              <span className="text-2xl font-bold tracking-tight" style={{ fontFamily: SERIF }}>
                WeAware
              </span>
            </div>
            
            <div className="text-[10px] font-mono tracking-widest uppercase bg-black text-white px-2 py-0.5">
              Secure Ingress
            </div>
          </div>

          {/* Main login card container */}
          <div className="my-auto max-w-md w-full mx-auto space-y-8 relative z-10 py-10">
            
            {/* Headers */}
            <div className="space-y-3">
              <h1 className="text-3xl font-black leading-tight tracking-tight uppercase" style={{ fontFamily: SERIF }}>
                {isSignUp ? "Create Ledger Identity" : "Verify Correspondent"}
              </h1>
              <p className="text-xs opacity-75 leading-relaxed">
                {isSignUp 
                  ? "Initialize your cryptographically verified contributor keys. An authorization invite hash is required."
                  : "To view clinical, bias-free reporting streams, authenticate your reporter keys or select Guest access."
                }
              </p>
            </div>

            {/* Success Message */}
            <AnimatePresence mode="wait">
              {successMessage && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="p-3.5 border-l-2 border-emerald-600 bg-emerald-500/10 text-xs font-mono text-emerald-900 flex items-center justify-between"
                >
                  <span>✅ {successMessage}</span>
                  <button onClick={() => setSuccessMessage("")} className="hover:opacity-60 text-[10px] font-bold">OK</button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Error Message */}
            <AnimatePresence mode="wait">
              {errorMessage && (
                <motion.div 
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="p-3.5 border-l-2 border-red-600 bg-red-500/10 text-xs font-mono text-red-950 flex items-center justify-between"
                >
                  <span>⚠️ ERROR: {errorMessage}</span>
                  <button onClick={() => setErrorMessage("")} className="hover:opacity-60 text-[10px] font-bold">DISMISS</button>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Authentication Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Email Address */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono tracking-wider uppercase opacity-75 block">
                  Credential / Email Node
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none opacity-60">
                    <User size={13} />
                  </span>
                  <input
                    type="email"
                    required
                    placeholder="editor@weaware.org"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-9 pr-4 py-3 bg-white/40 border border-black/15 text-sm focus:outline-none focus:border-black focus:bg-white transition-all rounded-none outline-none text-foreground"
                    style={{ borderColor: theme.border }}
                  />
                </div>
              </div>

              {/* Password */}
              <div className="space-y-1.5">
                <div className="flex justify-between items-center">
                  <label className="text-[10px] font-mono tracking-wider uppercase opacity-75">
                    Security Passphrase / Private Key
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="text-[9px] font-mono tracking-widest uppercase hover:underline opacity-60 hover:opacity-100 text-foreground"
                  >
                    {showPassword ? "Hide" : "Show"}
                  </button>
                </div>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none opacity-60">
                    <Lock size={13} />
                  </span>
                  <input
                    type={showPassword ? "text" : "password"}
                    required
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-9 pr-10 py-3 bg-white/40 border border-black/15 text-sm focus:outline-none focus:border-black focus:bg-white transition-all rounded-none outline-none text-foreground"
                    style={{ borderColor: theme.border }}
                  />
                </div>
              </div>

              {/* Full Name (Sign Up only) */}
              <AnimatePresence initial={false}>
                {isSignUp && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden space-y-1.5"
                  >
                    <label className="text-[10px] font-mono tracking-wider uppercase opacity-75 block">
                      Full Name / Display Handle
                    </label>
                    <div className="relative">
                      <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none opacity-60">
                        <User size={13} />
                      </span>
                      <input
                        type="text"
                        required
                        placeholder="Jane Correspondent"
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        className="w-full pl-9 pr-4 py-3 bg-white/40 border border-black/15 text-sm focus:outline-none focus:border-black focus:bg-white transition-all rounded-none outline-none text-foreground"
                        style={{ borderColor: theme.border }}
                      />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Submit Button (Sharp, Monospaced, tracked, high-contrast) */}
              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-4 text-xs font-mono font-bold tracking-widest uppercase transition-all duration-300 rounded-none shadow-none text-center flex items-center justify-center gap-2 border-none cursor-pointer"
                style={{
                  backgroundColor: theme.accent,
                  color: theme.accentFg,
                }}
              >
                {isSubmitting ? (
                  <span className="animate-pulse">AUTHENTICATING CIPHER KEYS...</span>
                ) : (
                  <>
                    {isSignUp ? "INITIALIZE LEDGER KEY" : "DECRYPT & ENTER PORTAL"}
                    <ArrowUpRight size={13} />
                  </>
                )}
              </button>
            </form>

            {/* Skip Option / Guest Mode */}
            <div className="relative flex py-2 items-center justify-center">
              <div className="flex-grow border-t border-black/10" style={{ borderColor: theme.border }} />
              <span className="flex-shrink mx-4 text-[9px] font-mono tracking-widest uppercase opacity-40">OR</span>
              <div className="flex-grow border-t border-black/10" style={{ borderColor: theme.border }} />
            </div>

            <button
              onClick={handleSkip}
              className="w-full py-3.5 border border-dashed text-xs font-mono font-semibold tracking-wider uppercase transition-colors bg-white/10 hover:bg-black/5 hover:border-black rounded-none flex items-center justify-center gap-1.5 cursor-pointer"
              style={{ borderColor: "rgba(3, 2, 19, 0.25)", color: theme.fg }}
            >
              <span>[ SKIP SESSION / ENTER GUEST MODE ]</span>
              <span>→</span>
            </button>

            {/* Account Toggle */}
            <div className="text-center pt-2">
              <button
                onClick={() => {
                  setIsSignUp(!isSignUp);
                  setErrorMessage("");
                }}
                className="text-xs font-mono tracking-wide underline opacity-70 hover:opacity-100 text-foreground cursor-pointer bg-transparent border-none"
              >
                {isSignUp 
                  ? "Already have verified credentials? Decrypt Portal"
                  : "Request credentials? Deploy new ledger account"
                }
              </button>
            </div>
          </div>

          {/* Bottom Security verification logs status */}
          <div className="mt-auto pt-6 border-t border-black/10 flex flex-col md:flex-row md:items-center justify-between text-[10px] font-mono opacity-65 gap-2" style={{ borderColor: theme.border }}>
            <div className="flex items-center gap-2">
              <Shield size={11} />
              <AnimatePresence mode="wait">
                {verificationIndex === 0 && (
                  <motion.span key="v1" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                    ✓ Encrypted Credential Verification Active
                  </motion.span>
                )}
                {verificationIndex === 1 && (
                  <motion.span key="v2" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                    ✓ Zero-Knowledge Proof Keypair Configured
                  </motion.span>
                )}
                {verificationIndex === 2 && (
                  <motion.span key="v3" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}>
                    ✓ Consensus Ledger Node Synchronized
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
            <div className="flex items-center gap-3">
              <span>SHA-256 Validated</span>
              <span>•</span>
              <span>TLS 1.3 Active</span>
            </div>
          </div>

        </div>

      </div>


    </motion.div>
  );
}
