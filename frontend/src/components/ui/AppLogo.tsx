import React from 'react';

interface AppLogoProps {
  /** Size of the brand mark in px. */
  size?: number;
}

/** Fixed brand-mark colors — theme-independent for consistent identity. */
const PETAL = '#3274F0';
const DOT = '#F59E0B';

/**
 * The AxiomFolio brand mark — the four-point star with amber center.
 * This IS the logo. "AxiomFolio" is the product name, rendered
 * separately wherever needed.
 */
const AppLogo: React.FC<AppLogoProps> = ({ size = 44 }) => {

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="AxiomFolio"
      role="img"
      style={{ shapeRendering: 'geometricPrecision', flexShrink: 0, display: 'block' }}
    >
      <path d="M64,14 C69,28 75,37 75,44 C75,50 70,55 64,55 C58,55 53,50 53,44 C53,37 59,28 64,14Z" fill={PETAL} />
      <path d="M114,64 C100,69 91,75 84,75 C78,75 73,70 73,64 C73,58 78,53 84,53 C91,53 100,59 114,64Z" fill={PETAL} />
      <path d="M64,114 C59,100 53,91 53,84 C53,78 58,73 64,73 C70,73 75,78 75,84 C75,91 69,100 64,114Z" fill={PETAL} />
      <path d="M14,64 C28,59 37,53 44,53 C50,53 55,58 55,64 C55,70 50,75 44,75 C37,75 28,69 14,64Z" fill={PETAL} />
      <circle cx="64" cy="64" r="6" fill={DOT} />
    </svg>
  );
};

export default AppLogo;
