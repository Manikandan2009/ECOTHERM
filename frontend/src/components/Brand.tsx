import { Link } from 'react-router-dom'

type BrandProps = {
  compact?: boolean
}

export default function Brand({ compact = false }: BrandProps) {
  return (
    <Link className={`brand${compact ? ' brand--compact' : ''}`} to="/" aria-label="Ecotherm home">
      <svg
        className="brand__mark"
        viewBox="0 0 42 42"
        aria-hidden="true"
      >
        <circle cx="27.5" cy="13.5" r="7.5" fill="#F2C879" />
        <path
          d="M7.2 29.8C7.2 17.4 18.3 8.5 31.7 9.2c.8 13.2-7.7 24.7-20.2 24.7-2.4 0-4.3-1.8-4.3-4.1Z"
          fill="#83D3A0"
        />
        <path d="M9.5 35c4.2-8.5 10.1-14.8 18.4-20" fill="none" stroke="#164B35" strokeWidth="2" strokeLinecap="round" />
        <path d="M19.2 23.1c-1.1-3.5-3.7-5.8-7.5-6.4M22.2 19.8c3.5.2 6.3 1.8 8.5 4.7" fill="none" stroke="#164B35" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <span className="brand__word">ECO<span>THERM</span></span>
    </Link>
  )
}
