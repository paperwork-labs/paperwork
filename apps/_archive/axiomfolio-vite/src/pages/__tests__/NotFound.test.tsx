import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { render, screen } from '@/test/testing-library';
import userEvent from '@testing-library/user-event';

import NotFound from '../NotFound';

describe('NotFound', () => {
  beforeEach(() => {
    vi.spyOn(window, 'dispatchEvent').mockImplementation(() => true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders headline and path', () => {
    render(
      <MemoryRouter initialEntries={['/missing-page']}>
        <Routes>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /wandered off the map/i })).toBeInTheDocument();
    expect(screen.getByText('/missing-page')).toBeInTheDocument();
  });

  it('Go home navigates to /', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/nope']}>
        <Routes>
          <Route path="/" element={<div>Home sweet home</div>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );
    await user.click(screen.getByRole('link', { name: /go home/i }));
    expect(screen.getByText('Home sweet home')).toBeInTheDocument();
  });

  it('Open Command Palette dispatches a Cmd/Ctrl+K keydown', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={['/bogus']}>
        <Routes>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );
    await user.click(screen.getByRole('button', { name: /open command palette/i }));
    expect(window.dispatchEvent).toHaveBeenCalled();
    const call = vi.mocked(window.dispatchEvent).mock.calls.find(([ev]) => ev instanceof KeyboardEvent);
    expect(call).toBeDefined();
    const ev = call![0] as KeyboardEvent;
    expect(ev.type).toBe('keydown');
    expect(ev.key).toBe('k');
  });

  it('renders NotFound for an unknown route in a small route tree', () => {
    render(
      <MemoryRouter initialEntries={['/this-route-does-not-exist']}>
        <Routes>
          <Route path="/" element={<div>ok</div>} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByRole('heading', { name: /wandered off the map/i })).toBeInTheDocument();
  });
});
