import { motion, useReducedMotion } from 'framer-motion'
import { Link } from 'react-router-dom'
import Brand from '../components/Brand'
import Landscape from '../components/Landscape'

const features = [
  { icon: '◉', label: 'Satellite heat mapping' },
  { icon: '✳', label: 'AI heat-risk prediction' },
  { icon: '↗', label: 'Cooling recommendations' },
]

export default function Landing() {
  const reduceMotion = useReducedMotion()
  const reveal = (delay: number) => ({
    initial: reduceMotion ? false : { opacity: 0, y: 18 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: reduceMotion ? 0 : 0.7, delay: reduceMotion ? 0 : delay, ease: 'easeOut' as const },
  })

  return (
    <main className="landing">
      <Landscape />
      <div className="ambient ambient--one" aria-hidden="true" />
      <div className="ambient ambient--two" aria-hidden="true" />
      <div className="leaf-particles" aria-hidden="true">
        <span className="leaf-particle leaf-particle--one" />
        <span className="leaf-particle leaf-particle--two" />
        <span className="leaf-particle leaf-particle--three" />
      </div>

      <header className="topbar">
        <Brand />
        <div className="topbar__note">
          <span className="status-dot" />
          <span>Urban climate intelligence</span>
        </div>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <motion.div className="hero__eyebrow" {...reveal(0.1)}>
          <span className="eyebrow-line" />
          DATA FOR A COOLER TOMORROW
          <span className="eyebrow-line" />
        </motion.div>
        <motion.h1 id="hero-title" {...reveal(0.2)}>
          Welcome to
          <span className="hero__title-accent">Ecotherm<span className="hero__period">.</span></span>
        </motion.h1>
        <motion.p className="hero__tagline" {...reveal(0.38)}>
          Building Cooler, Greener and
          <br className="desktop-break" /> More Sustainable Cities.
        </motion.p>
        <motion.p className="hero__description" {...reveal(0.5)}>
          Turn Earth observation and environmental data into
          <br className="desktop-break" /> actionable insight for healthier urban futures.
        </motion.p>
        <motion.div className="hero__actions" {...reveal(0.62)}>
          <Link className="button-primary" to="/dashboard">
            <span>Get Started</span>
            <svg viewBox="0 0 20 20" aria-hidden="true">
              <path d="M3.5 10h12m-5-5 5 5-5 5" />
            </svg>
          </Link>
        </motion.div>
        <motion.ul className="feature-list" aria-label="Platform capabilities" {...reveal(0.76)}>
          {features.map((feature) => (
            <li className="feature-chip" key={feature.label}>
              <span className="feature-chip__icon" aria-hidden="true">{feature.icon}</span>
              {feature.label}
            </li>
          ))}
        </motion.ul>
      </section>

      <motion.div className="scroll-cue" {...reveal(1)}>
        <span className="scroll-cue__line" />
        A CLEARER VIEW OF OUR CITIES
      </motion.div>
      <footer className="landing-footer">
        <span>© {new Date().getFullYear()} ECOTHERM</span>
        <span>Insight for a more resilient urban future</span>
      </footer>
    </main>
  )
}
