import { useId } from 'react'

// Prognova mark: three rising towers with a four-point "nova" star above the tallest.
export function Logo({ size = 32 }: { size?: number }) {
  const uid = useId().replace(/:/g, '')
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden focusable="false">
      <defs>
        <linearGradient id={`bg${uid}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#263a66" />
          <stop offset="1" stopColor="#1d2b4f" />
        </linearGradient>
        <linearGradient id={`bar${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#8fd0fa" />
          <stop offset="1" stopColor="#1f8fd8" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill={`url(#bg${uid})`} />
      <rect x=".5" y=".5" width="39" height="39" rx="10.5" fill="none" stroke="#5aaee6" strokeOpacity=".5" />
      <rect x="8" y="22" width="5.5" height="11" rx="1.6" fill={`url(#bar${uid})`} opacity=".75" />
      <rect x="16.5" y="17" width="5.5" height="16" rx="1.6" fill={`url(#bar${uid})`} opacity=".9" />
      <rect x="25" y="20" width="5.5" height="13" rx="1.6" fill="#f0a020" />
      <path d="M27.75 6.5 L29.1 10.4 L33 11.75 L29.1 13.1 L27.75 17 L26.4 13.1 L22.5 11.75 L26.4 10.4 Z" fill="#ffd38a" />
    </svg>
  )
}
