import './App.css'
import heroImage from './assets/hero.png'

function App() {
  return (
    <main className="landing-page">
      <div className="video-shell">
        <img
          className="intro-video"
          src={heroImage}
          alt="WeAware News hero"
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
