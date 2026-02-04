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
      title: '28+ World-Class Resorts',
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
    { number: '28+', label: 'Resorts' },
    { number: '8', label: 'Regions' },
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
                  href="https://apps.apple.com/app/powder-chaser"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn btn-primary"
                >
                  <BsApple size={20} />
                  Download on App Store
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
              <div className="quality-badge excellent">Excellent</div>
              <p>3+ inches of fresh powder since last ice event. Cold temps preserving quality. Perfect conditions for all skiing.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge good">Good</div>
              <p>2+ inches of non-refrozen snow. Surface hasn't iced over. Great for on and off-piste skiing.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge fair">Fair</div>
              <p>~1 inch fresh on older base. May have thin crust in places. Groomed runs in good shape.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge poor">Poor</div>
              <p>Less than 1 inch since last ice event. Harder surface with some soft spots. Stick to groomers.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge bad">Icy</div>
              <p>No fresh snow since last thaw-freeze cycle. Hard, refrozen surface. Challenging conditions.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge horrible">Not Skiable</div>
              <p>Dangerous conditions: no snow cover, actively melting, or exposed terrain. Resort may be closed.</p>
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
                href="https://apps.apple.com/app/powder-chaser"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-white"
              >
                <BsApple size={20} />
                Download for iOS
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
