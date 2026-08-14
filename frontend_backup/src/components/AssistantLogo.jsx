export default function AssistantLogo({ className = "assistant-logo", compact = false }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Logo assistant IA"
    >
      <defs>
        <linearGradient id="assistantGlow" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#77d4ff" />
          <stop offset="100%" stopColor="#2f7db8" />
        </linearGradient>
        <linearGradient id="assistantCore" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f5fbff" />
          <stop offset="100%" stopColor="#d6edfb" />
        </linearGradient>
      </defs>

      <rect x="6" y="8" width="52" height="48" rx="16" fill="url(#assistantGlow)" />
      <rect x="12" y="14" width="40" height="36" rx="12" fill="url(#assistantCore)" />
      <path
        d="M24 24h16M24 31h12M24 38h9"
        fill="none"
        stroke="#2f698c"
        strokeLinecap="round"
        strokeWidth="3.2"
      />
      <circle cx="47" cy="21" r="7" fill="#fff8ef" stroke="#1f6597" strokeWidth="2.5" />
      <path
        d="M47 16.5v9M42.5 21h9"
        fill="none"
        stroke="#1f6597"
        strokeLinecap="round"
        strokeWidth="2.4"
      />
      {!compact ? (
        <path
          d="M24 52l-5 7 11-4"
          fill="none"
          stroke="#2f7db8"
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="3"
        />
      ) : null}
    </svg>
  );
}
