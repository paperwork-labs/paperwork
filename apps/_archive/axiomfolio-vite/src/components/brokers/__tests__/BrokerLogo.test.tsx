import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/testing-library';
import { BrokerLogo } from '../BrokerLogo';
import { BROKER_LOGO_SLUGS } from '../brokerLogosMap';

describe('BrokerLogo', () => {
  for (const slug of BROKER_LOGO_SLUGS) {
    it(`renders a bundled mark for ${slug} without error`, () => {
      const { container } = render(
        <BrokerLogo slug={slug} name={`Test ${slug}`} size={32} />,
      );
      expect(container.querySelector('img')).toBeInTheDocument();
    });
  }

  it('exposes a consistent accessible name for bundled logos', () => {
    render(<BrokerLogo slug="schwab" name="Charles Schwab" size={32} />);
    expect(screen.getByRole('img', { name: 'Charles Schwab logo' })).toBeInTheDocument();
  });

  it('uses Building2 (not a broken image) for unknown slugs with no URL', () => {
    const { container } = render(
      <BrokerLogo slug="totally_unknown_broker_xyz" name="Mystery Co" size={32} />,
    );
    expect(container.querySelector('img')).not.toBeInTheDocument();
    const icon = container.querySelector('svg');
    expect(icon).toBeTruthy();
    expect(screen.getByRole('img', { name: 'Mystery Co logo' })).toBeInTheDocument();
  });
});
