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
} from 'react-icons/fi'
import { BsApple, BsSnow } from 'react-icons/bs'

function HomePage() {
  const features = [
    {
      icon: <BsSnow />,
      title: 'Real-Time Snow Quality',
      description: 'Our algorithm analyzes temperature, snowfall, and freeze-thaw cycles to rate snow from Excellent to Icy.'
    },
    {
      icon: <FiMapPin />,
      title: '28+ World-Class Resorts',
      description: 'Track conditions at top resorts across North America, the Alps, Japan, and more.'
    },
    {
      icon: <FiSun />,
      title: 'Fresh Powder Tracking',
      description: 'Know exactly how much non-refrozen snow is on the mountain. Find the freshest lines.'
    },
    {
      icon: <FiCloud />,
      title: 'Weather Forecasts',
      description: 'See predicted snowfall for the next 24-72 hours. Plan your powder days in advance.'
    },
    {
      icon: <FiStar />,
      title: 'Favorite Resorts',
      description: 'Save your favorite mountains and see their conditions at a glance on your home screen.'
    },
    {
      icon: <FiSmartphone />,
      title: 'iOS Widgets',
      description: 'Beautiful home screen widgets showing conditions at your favorite resorts.'
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

      {/* How It Works Section */}
      <section className="how-it-works">
        <div className="container">
          <div className="section-header">
            <h2>How <span className="text-gradient">snow quality</span> works</h2>
            <p>Our algorithm tracks what really matters for skiing.</p>
          </div>

          <div className="quality-explainer">
            <div className="quality-item">
              <div className="quality-badge excellent">Excellent</div>
              <p>3+ inches of fresh powder on top. No recent thaw-freeze. Perfect conditions.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge good">Good</div>
              <p>2+ inches of non-refrozen snow. Surface is soft. Great for all-mountain skiing.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge fair">Fair</div>
              <p>Some fresh snow on top of older base. Groomed runs in good shape.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge poor">Poor</div>
              <p>Thin fresh snow cover. Harder surface with some soft spots.</p>
            </div>
            <div className="quality-item">
              <div className="quality-badge bad">Icy</div>
              <p>No fresh snow since last thaw-freeze. Hard, refrozen surface.</p>
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
            </div>
          </div>
        </div>
      </section>
    </>
  )
}

export default HomePage
