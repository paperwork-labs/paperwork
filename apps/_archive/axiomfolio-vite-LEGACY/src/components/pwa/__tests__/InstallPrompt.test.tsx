import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { InstallPrompt } from '../InstallPrompt'

describe('InstallPrompt', () => {
  it('renders nothing when canPrompt is false (default state)', () => {
    const { container } = render(<InstallPrompt />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the install affordance when forceVisible is set', () => {
    render(<InstallPrompt forceVisible />)
    expect(screen.getByRole('dialog', { name: /install axiomfolio/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dismiss install prompt/i })).toBeInTheDocument()
  })
})
