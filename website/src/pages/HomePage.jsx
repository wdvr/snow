import { Link } from 'react-router-dom'
import {
  FiSun,
  FiCloud,
  FiMapPin,
  FiStar,
  FiBell,
  FiSmartphone,
  FiGithub,
  FiMessageCircle,
  FiCpu,
  FiThermometer,
  FiCoffee,
  FiGlobe,
} from 'react-icons/fi'
import { BsApple, BsSnow } from 'react-icons/bs'

function HomePage() {
  const features = [
    {
      icon: <FiCpu />,
      title: 'Proprietary Snow Algorithm',
      description: 'Our advanced algorithm goes beyond basic snowfall data to calculate actual skiable snow quality in real-time.'
    },
    {
      icon: <BsSnow />,
      title: 'Fresh Powder Tracking',
      description: 'We track snow since the last ice formation event. Not just snowfall, but actual non-refrozen powder depth.'
    },
    {
      icon: <FiThermometer />,
      title: 'Ice Layer Detection',
      description: 'Multi-threshold freeze-thaw analysis detects when snow becomes icy (3h@3°C, 6h@2°C, or 8h@1°C).'
    },
    {
      icon: <FiMapPin />,
      title: '130+ World-Class Resorts',
      description: 'Track conditions at top resorts across North America, the Alps, Japan, and more.'
    },
    {
      icon: <FiCloud />,
      title: '72h Forecasts',
      description: 'See predicted snowfall for the next 24-72 hours. Plan your powder days in advance.'
    },
    {
      icon: <FiSmartphone />,
      title: 'iOS Widgets',
      description: 'Beautiful home screen widgets showing real-time snow quality at your favorite resorts.'
    }
  ]

  const stats = [
    { number: '130+', label: 'Resorts' },
    { number: '11', label: 'Countries' },
    { number: '24/7', label: 'Updates' },
    { number: '100%', label: 'Free' }
  ]

  return (
    <>
      {/* Hero Section */}
      <section className="hero">
        <div className="container">
          <div className="hero-content">
            <div className="hero-text">
              <h1>
                Chase the
                <br />
                <span className="text-gradient">freshest powder.</span>
              </h1>
              <p>
                Real-time snow quality tracking for ski resorts worldwide.
                Know when conditions are perfect before you go.
              </p>
              <div className="hero-buttons">
                <a
                  href="https://apps.apple.com/app/powder-chaser/id6758333173"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                >
                  <BsApple size={20} />
                  Download on App Store
                </a>
                <a
                  href="https://app.powderchaserapp.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                >
                  <FiGlobe size={20} />
                  Open Web App
                </a>
                <a
                  href="https://github.com/wdvr/snow"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-secondary"
                >
                  <FiGithub size={20} />
                  View on GitHub
                </a>
              </div>
            </div>

            <div className="hero-visual">
              <img
                src="/screenshot-iphone.png"
                alt="Powder Chaser app showing snow conditions at ski resorts"
                className="hero-screenshot"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="container">
        <div className="stats">
          {stats.map((stat, index) => (
            <div key={index} className="stat-item">
              <div className="stat-number">{stat.number}</div>
              <div className="stat-label">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section className="features" id="features">
        <div className="container">
          <div className="section-header">
            <h2>Everything you need to <span className="text-gradient">find perfect snow</span></h2>
            <p>Smart algorithms that understand what makes great skiing conditions.</p>
          </div>

          <div className="features-grid">
            {features.map((feature, index) => (
              <div key={index} className="card feature-card">
                <div className="feature-icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Algorithm Section */}
      <section className="algorithm">
        <div className="container">
          <div className="section-header">
            <h2>Our <span className="text-gradient">Proprietary Algorithm</span></h2>
            <p>Other apps show you snowfall. We show you actual skiing conditions.</p>
          </div>

          <div className="algorithm-explainer">
            <div className="algorithm-card">
              <h3>Why Snowfall Data Isn't Enough</h3>
              <p>
                10 inches of snow means nothing if it refroze overnight. Most weather apps
                ignore the science of snow metamorphosis. Powder Chaser tracks what actually
                matters: <strong>how much non-refrozen snow sits on top of the last ice layer</strong>.
              </p>
            </div>

            <div className="algorithm-features">
              <div className="algo-feature">
                <div className="algo-icon">🧊</div>
                <h4>Ice Layer Detection</h4>
                <p>We model ice formation using multiple temperature thresholds: 3 hours at 3°C, 6 hours at 2°C, or 8 hours at 1°C. When the surface refreezes, we reset the fresh powder counter.</p>
              </div>
              <div className="algo-feature">
                <div className="algo-icon">❄️</div>
                <h4>Fresh Powder Accumulation</h4>
                <p>After each freeze-thaw event, we track all new snowfall as "non-refrozen snow." This is the actual skiable powder depth that determines your experience.</p>
              </div>
              <div className="algo-feature">
                <div className="algo-icon">🌡️</div>
                <h4>Real-Time Temperature Analysis</h4>
                <p>Continuous monitoring of temperature trends lets us predict when conditions are degrading or improving, not just show you the current state.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works">
        <div className="container">
          <div className="section-header">
            <h2>How <span className="text-gradient">snow quality</span> ratings work</h2>
            <p>Our algorithm converts complex weather data into actionable ratings.</p>
          </div>

          <div className="quality-explainer">
            <div className="quality-item">
              <div className="quality-badge champagne-powder">Champagne Powder</div>
              <p>Ultra-light, dry powder. Dream conditions — deep, untracked freshies everywhere.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge powder-day">Powder Day</div>
              <p>Significant fresh snowfall. Excellent coverage and soft snow on and off-piste.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge excellent">Excellent</div>
              <p>Recent snowfall with cold temps preserving quality. Great skiing across the mountain.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge great">Great</div>
              <p>Good snow coverage with some fresh. Mostly soft conditions, great on groomers.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge good">Good</div>
              <p>Decent base with some recent snow. Enjoyable skiing, especially on prepared runs.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge decent">Decent</div>
              <p>Adequate conditions. Some firm spots but overall rideable. Stick to groomers.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge mediocre">Mediocre</div>
              <p>Limited fresh snow, aging base. Variable surface quality across the mountain.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge poor">Poor</div>
              <p>Hard pack or thin cover. Icy patches likely. Only groomed runs advisable.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge bad">Bad</div>
              <p>Mostly icy or very thin coverage. Challenging conditions for any ability level.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge horrible">Not Skiable</div>
              <p>Dangerous: no snow cover, actively melting, or closed terrain.</p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta">
        <div className="container">
          <div className="cta-box">
            <h2>Ready to find better snow?</h2>
            <p>Download Powder Chaser for free and never miss a powder day again.</p>
            <div className="cta-buttons">
              <a
                href="https://apps.apple.com/app/powder-chaser/id6758333173"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-white"
              >
                <BsApple size={20} />
                Download for iOS
              </a>
              <a
                href="https://app.powderchaserapp.com"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-white"
              >
                <FiGlobe size={20} />
                Open Web App
              </a>
              <a
                href="https://buymeacoffee.com/wdvr"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary"
              >
                <FiCoffee size={20} />
                Buy Me a Coffee
              </a>
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

export default HomePage
