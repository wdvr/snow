function TermsPage() {
  return (
    <div className="legal-page">
      <div className="container">
        <div className="legal-content">
          <h1>Terms of Service</h1>
          <p className="last-updated">Last updated: January 2026</p>

          <p>
            Welcome to Powder Chaser! These Terms of Service ("Terms") govern your use of the Powder Chaser
            mobile application ("App") and related services provided by Powder Chaser ("we", "us", or "our").
          </p>

          <h2>1. Acceptance of Terms</h2>
          <p>
            By downloading, installing, or using Powder Chaser, you agree to be bound by these Terms.
            If you do not agree to these Terms, please do not use the App.
          </p>

          <h2>2. Description of Service</h2>
          <p>
            Powder Chaser is a snow condition tracking application that allows you to:
          </p>
          <ul>
            <li>View current snow conditions and quality ratings at ski resorts worldwide</li>
            <li>Track fresh snowfall, temperature, and weather forecasts</li>
            <li>Save favorite resorts for quick access</li>
            <li>Use widgets to see conditions on your home screen</li>
            <li>Find nearby ski resorts based on your location (optional)</li>
          </ul>

          <h2>3. No Account Required</h2>
          <p>
            Powder Chaser does not require account creation. All preferences are stored locally on
            your device. You may use all features without providing any personal information.
          </p>

          <h2>4. User Conduct</h2>
          <p>You agree not to:</p>
          <ul>
            <li>Use the App for any unlawful purpose</li>
            <li>Attempt to gain unauthorized access to our systems or APIs</li>
            <li>Interfere with or disrupt the App's functionality</li>
            <li>Reverse engineer, decompile, or disassemble the App</li>
            <li>Use automated systems to access the App without permission</li>
            <li>Scrape or harvest data from the App for commercial purposes</li>
          </ul>

          <h2>5. Weather Data Disclaimer</h2>
          <p>
            <strong>IMPORTANT:</strong> Snow conditions and weather data provided by Powder Chaser are
            estimates based on publicly available weather data and our snow quality algorithm. This
            information should be used for planning purposes only.
          </p>
          <ul>
            <li>Always check official resort reports before traveling</li>
            <li>Conditions can change rapidly in mountain environments</li>
            <li>We do not guarantee the accuracy of any weather or snow data</li>
            <li>Skiing and snowboarding are inherently dangerous activities</li>
          </ul>

          <h2>6. Intellectual Property</h2>
          <p>
            The App and its original content, features, and functionality are owned by Powder Chaser
            and are protected by international copyright, trademark, and other intellectual property laws.
            The source code is available under open source license on GitHub, but visual assets,
            branding, and the "Powder Chaser" name remain proprietary.
          </p>

          <h2>7. Third-Party Services</h2>
          <p>
            The App integrates with third-party services including:
          </p>
          <ul>
            <li>Open-Meteo API for weather data</li>
            <li>Apple MapKit for map functionality</li>
            <li>AWS for backend infrastructure</li>
          </ul>
          <p>
            Your use of these services is subject to their respective terms and privacy policies.
          </p>

          <h2>8. Disclaimer of Warranties</h2>
          <p>
            THE APP IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER
            EXPRESS OR IMPLIED. WE DO NOT WARRANT THAT THE APP WILL BE UNINTERRUPTED, ERROR-FREE,
            OR ACCURATE. WEATHER AND SNOW DATA ARE ESTIMATES AND SHOULD NOT BE RELIED UPON FOR
            SAFETY-CRITICAL DECISIONS.
          </p>

          <h2>9. Limitation of Liability</h2>
          <p>
            TO THE MAXIMUM EXTENT PERMITTED BY LAW, WE SHALL NOT BE LIABLE FOR ANY INDIRECT,
            INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING FROM YOUR USE OF THE APP.
            THIS INCLUDES, WITHOUT LIMITATION, DAMAGES ARISING FROM RELIANCE ON WEATHER OR SNOW
            CONDITION DATA, TRAVEL DECISIONS, OR SKIING/SNOWBOARDING ACTIVITIES.
          </p>

          <h2>10. Assumption of Risk</h2>
          <p>
            You acknowledge that skiing, snowboarding, and other mountain activities involve inherent
            risks including serious injury or death. You assume all risks associated with these
            activities and agree that Powder Chaser is not responsible for any injuries or damages
            resulting from your participation in such activities.
          </p>

          <h2>11. Changes to Terms</h2>
          <p>
            We may modify these Terms at any time. We will notify you of significant changes through
            the App or website. Your continued use of the App after changes constitutes acceptance
            of the modified Terms.
          </p>

          <h2>12. Termination</h2>
          <p>
            We may terminate or suspend your access to the App at any time, without prior notice,
            for conduct that we believe violates these Terms or is harmful to other users or us.
          </p>

          <h2>13. Governing Law</h2>
          <p>
            These Terms shall be governed by and construed in accordance with the laws of Belgium,
            without regard to conflict of law principles.
          </p>

          <h2>14. Contact Us</h2>
          <p>
            If you have any questions about these Terms, please contact us through the feedback
            form in the App or via our GitHub repository.
          </p>
        </div>
      </div>
    </div>
  )
}

export default TermsPage
