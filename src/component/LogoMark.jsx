"use client";

export default function LogoMark({ collapsed }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        overflow: 'hidden',
        userSelect: 'none',
        paddingLeft: 4,
      }}
    >
      {/* logo.png always visible */}
      <img
        src="/logo.png"
        alt="Airi"
        style={{
          width: 28,
          height: 28,
          objectFit: 'contain',
          flexShrink: 0,
          borderRadius: 6,
        }}
      />
      {/* "Airi" text — only when expanded */}
      <span
        style={{
          fontFamily: 'var(--font-logo)',
          fontSize: '20px',
          color: 'var(--text-primary)',
          display: 'inline-block',
          overflow: 'hidden',
          maxWidth: collapsed ? '0px' : '80px',
          opacity: collapsed ? 0 : 1,
          transition: 'max-width 250ms ease-in-out, opacity 200ms ease-in-out',
          whiteSpace: 'nowrap',
          lineHeight: 1,
        }}
      >
        Airi
      </span>
    </div>
  );
}
