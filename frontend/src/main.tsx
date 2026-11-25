import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import 'leaflet/dist/leaflet.css'
import './styles.css'

const baseUrl = new URL(import.meta.env.BASE_URL, window.location.origin)
const redirect = new URLSearchParams(window.location.search).get('redirect')

if (redirect !== null) {
  const destination = new URL(redirect, baseUrl)
  const basePath = baseUrl.pathname.endsWith('/')
    ? baseUrl.pathname
    : `${baseUrl.pathname}/`

  if (
    destination.origin === window.location.origin
    && (destination.pathname === baseUrl.pathname || destination.pathname.startsWith(basePath))
  ) {
    window.history.replaceState(
      null,
      '',
      `${destination.pathname}${destination.search}${destination.hash}`,
    )
  } else {
    window.history.replaceState(null, '', baseUrl.pathname)
  }
}

const basename = baseUrl.pathname === '/'
  ? '/'
  : baseUrl.pathname.replace(/\/$/, '')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
