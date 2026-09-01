import './App.css'
import introVideo from './assets/Intro.mov'

function App() {
  return (
    <main className="landing-page">
      <div className="video-shell">
        <video
          className="intro-video"
          src={introVideo}
          autoPlay
          muted
          loop
          playsInline
          preload="auto"
          aria-label="Intro video"
        />

        <div className="video-overlay">
          <p className="eyebrow">Breaking down the noise</p>
          <h1 className="headline">
            WeAware News: <span className="highlight-wrap"><span className="highlight">Completely Autonomous</span></span> Unbiased News
          </h1>
        </div>
      </div>
    </main>
  )
}

export default App
