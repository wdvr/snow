import { useState } from 'react'
import { FiMail, FiMessageCircle, FiGithub, FiSend, FiCheckCircle } from 'react-icons/fi'

function SupportPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: '',
    message: ''
  })
  const [submitted, setSubmitted] = useState(false)
  const [sending, setSending] = useState(false)

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSending(true)

    // Submit to backend feedback endpoint
    try {
      const response = await fetch('https://api.powderchaserapp.com/api/v1/feedback', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: 'support',
          email: formData.email,
          name: formData.name,
          subject: formData.subject,
          message: formData.message,
        }),
      })

      if (response.ok) {
        setSubmitted(true)
      } else {
        // Fallback to mailto if API fails
        window.location.href = `mailto:support@powderchaserapp.com?subject=${encodeURIComponent(formData.subject)}&body=${encodeURIComponent(`From: ${formData.name} (${formData.email})\n\n${formData.message}`)}`
      }
    } catch (error) {
      // Fallback to mailto if API fails
      window.location.href = `mailto:support@powderchaserapp.com?subject=${encodeURIComponent(formData.subject)}&body=${encodeURIComponent(`From: ${formData.name} (${formData.email})\n\n${formData.message}`)}`
    }

    setSending(false)
  }

  if (submitted) {
    return (
      <section className="support-page">
        <div className="container">
          <div className="support-success">
            <FiCheckCircle size={64} className="success-icon" />
            <h1>Message Sent!</h1>
            <p>Thanks for reaching out. We'll get back to you as soon as possible.</p>
            <a href="/" className="btn btn-primary">Back to Home</a>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className="support-page">
      <div className="container">
        <div className="support-header">
          <h1>Get in Touch</h1>
          <p>Have a question, found a bug, or want to request a feature? We'd love to hear from you.</p>
        </div>

        <div className="support-content">
          <div className="support-options">
            <div className="support-option">
              <FiMail size={32} />
              <h3>Email Us</h3>
              <p>Send us an email directly and we'll respond within 24 hours.</p>
              <a href="mailto:support@powderchaserapp.com" className="btn btn-secondary">
                support@powderchaserapp.com
              </a>
            </div>

            <div className="support-option">
              <FiGithub size={32} />
              <h3>GitHub Issues</h3>
              <p>Report bugs or request features on our open source repository.</p>
              <a
                href="https://github.com/wdvr/snow/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-secondary"
              >
                Open an Issue
              </a>
            </div>
          </div>

          <div className="support-form-container">
            <h2>Send us a Message</h2>
            <form onSubmit={handleSubmit} className="support-form">
              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="name">Name</label>
                  <input
                    type="text"
                    id="name"
                    name="name"
                    value={formData.name}
                    onChange={handleChange}
                    required
                    placeholder="Your name"
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="email">Email</label>
                  <input
                    type="email"
                    id="email"
                    name="email"
                    value={formData.email}
                    onChange={handleChange}
                    required
                    placeholder="your@email.com"
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="subject">Subject</label>
                <select
                  id="subject"
                  name="subject"
                  value={formData.subject}
                  onChange={handleChange}
                  required
                >
                  <option value="">Select a topic...</option>
                  <option value="Bug Report">Bug Report</option>
                  <option value="Feature Request">Feature Request</option>
                  <option value="Resort Request">Request a Resort</option>
                  <option value="Account Issue">Account Issue</option>
                  <option value="General Question">General Question</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="message">Message</label>
                <textarea
                  id="message"
                  name="message"
                  value={formData.message}
                  onChange={handleChange}
                  required
                  rows={6}
                  placeholder="Tell us how we can help..."
                />
              </div>

              <button type="submit" className="btn btn-primary" disabled={sending}>
                <FiSend size={18} />
                {sending ? 'Sending...' : 'Send Message'}
              </button>
            </form>
          </div>
        </div>

        <div className="support-faq">
          <h2>Frequently Asked Questions</h2>
          <div className="faq-grid">
            <div className="faq-item">
              <h4>How accurate is the snow quality data?</h4>
              <p>We use data from Open-Meteo combined with our proprietary algorithm that tracks freeze-thaw cycles. Accuracy varies by resort but is generally within 1-2 inches of actual conditions.</p>
            </div>
            <div className="faq-item">
              <h4>Can you add my local resort?</h4>
              <p>Yes! Use the contact form above with "Request a Resort" selected. Include the resort name, location, and website if available.</p>
            </div>
            <div className="faq-item">
              <h4>Is the app free?</h4>
              <p>Yes, Powder Chaser is completely free with no ads or in-app purchases. We're skiers who built this for the community.</p>
            </div>
            <div className="faq-item">
              <h4>Why does my resort show different snow than the resort website?</h4>
              <p>Resort websites often report total base depth, while we show fresh non-refrozen snow. A resort might have 100" base but only 2" of skiable powder on top.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default SupportPage
