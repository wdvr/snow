function PrivacyPage() {
  return (
    <div className="legal-page">
      <div className="container">
        <div className="legal-content">
          <h1>Privacy Policy</h1>
          <p className="last-updated">Last updated: January 2026</p>

          <p>
            Your privacy is important to us. This Privacy Policy explains how Powder Chaser ("we", "us",
            or "our") collects, uses, and protects your information when you use our mobile application
            ("App").
          </p>

          <h2>1. Information We Collect</h2>

          <h3>1.1 Information You Provide</h3>
          <ul>
            <li>
              <strong>Favorite Resorts:</strong> The ski resorts you mark as favorites to track conditions.
            </li>
            <li>
              <strong>Feedback:</strong> Information you provide when contacting us through feedback forms,
              including your email if you choose to provide it.
            </li>
          </ul>

          <h3>1.2 Information Collected Automatically</h3>
          <ul>
            <li>
              <strong>Device Information:</strong> Device type, operating system version, and app version
              for troubleshooting and compatibility purposes.
            </li>
            <li>
              <strong>Location Data:</strong> Only when you explicitly enable location services to
              show nearby ski resorts and calculate distances. Location data is processed locally
              on your device and not stored on our servers.
            </li>
            <li>
              <strong>Usage Analytics:</strong> Anonymous, aggregated usage statistics to improve the App.
              No personally identifiable information is included.
            </li>
          </ul>

          <h2>2. How We Use Your Information</h2>
          <p>We use your information to:</p>
          <ul>
            <li>Provide and maintain the App's functionality</li>
            <li>Show you conditions for your favorite resorts</li>
            <li>Display nearby resorts when location is enabled</li>
            <li>Respond to your feedback and support requests</li>
            <li>Improve the App based on usage patterns</li>
            <li>Ensure the security and integrity of our services</li>
          </ul>

          <h2>3. Data Storage and Security</h2>

          <h3>3.1 Local Storage</h3>
          <p>
            Your favorite resorts and preferences are stored locally on your device. The App works
            fully offline for viewing cached conditions.
          </p>

          <h3>3.2 Weather Data</h3>
          <p>
            Snow conditions and weather data are fetched from our servers, which aggregate data from
            public weather APIs. This data is not personally identifiable.
          </p>

          <h3>3.3 Security Measures</h3>
          <ul>
            <li>Encrypted data transmission (TLS/HTTPS)</li>
            <li>No account or login required</li>
            <li>Minimal data collection</li>
          </ul>

          <h2>4. Data Sharing</h2>
          <p>We do not sell your personal information. We may share data only in these circumstances:</p>
          <ul>
            <li>
              <strong>Service Providers:</strong> With trusted third parties who help us operate
              the App (e.g., AWS for hosting), bound by confidentiality agreements.
            </li>
            <li>
              <strong>Weather Data Sources:</strong> We use Open-Meteo API for weather data. Your
              requests are anonymized.
            </li>
            <li>
              <strong>Legal Requirements:</strong> When required by law or to protect our rights.
            </li>
          </ul>

          <h2>5. Your Rights</h2>
          <p>You have the right to:</p>
          <ul>
            <li>
              <strong>Access:</strong> View your stored preferences in the App settings
            </li>
            <li>
              <strong>Deletion:</strong> Clear all local data by uninstalling the App
            </li>
            <li>
              <strong>Opt-out:</strong> Disable location services at any time in your device settings
            </li>
          </ul>

          <h2>6. Data Retention</h2>
          <p>
            We retain feedback submissions for up to 2 years to improve the App. Anonymous usage
            analytics are retained indefinitely in aggregated form. Local device data is retained
            until you uninstall the App.
          </p>

          <h2>7. Children's Privacy</h2>
          <p>
            The App is not intended for children under 13. We do not knowingly collect information
            from children under 13. If you believe we have collected such information, please contact us.
          </p>

          <h2>8. International Data Transfers</h2>
          <p>
            Our servers are located in the United States (AWS us-west-2). If you access the App from
            outside the US, your data may be transferred to and processed in the US.
          </p>

          <h2>9. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify you of significant
            changes through the App. Your continued use after changes constitutes acceptance.
          </p>

          <h2>10. Contact Us</h2>
          <p>
            If you have questions about this Privacy Policy, please contact us via the feedback
            form in the App or through our GitHub repository.
          </p>

          <h2>11. California Residents (CCPA)</h2>
          <p>
            California residents have additional rights under the CCPA, including the right to know
            what personal information is collected and the right to opt-out of the sale of personal
            information. Note: we do not sell personal information.
          </p>

          <h2>12. European Residents (GDPR)</h2>
          <p>
            If you are in the European Economic Area, you have additional rights under the GDPR,
            including the right to lodge a complaint with a supervisory authority. Our legal basis
            for processing is legitimate interest in providing and improving the App.
          </p>
        </div>
      </div>
    </div>
  )
}

export default PrivacyPage
