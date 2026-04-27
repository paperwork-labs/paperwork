/**
 * Re-exports for React 19 compatibility.
 * screen, fireEvent, waitFor come from @testing-library/dom to satisfy React 19 types.
 */
export { render, cleanup } from '@testing-library/react';
export { screen, fireEvent, waitFor } from '@testing-library/dom';
