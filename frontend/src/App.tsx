import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Landing from './pages/Landing'

export default function App() {
  const location = useLocation()
  const reduceMotion = useReducedMotion()

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        className="route-shell"
        initial={reduceMotion ? false : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduceMotion ? undefined : { opacity: 0, y: -8 }}
        transition={{ duration: reduceMotion ? 0 : 0.3, ease: 'easeOut' }}
      >
        <Routes location={location}>
          <Route path="/" element={<Landing />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  )
}
