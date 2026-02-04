import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { LoginPage } from './login'
import { BrowserRouter } from 'react-router-dom'

// Mock axios
vi.mock('axios', () => ({
  default: {
    get: vi.fn(),
  },
}))

import axios from 'axios'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders login form', () => {
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    )
    
    expect(screen.getByText('TeachProxy Admin')).toBeInTheDocument()
    expect(screen.getByLabelText('Admin Token')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument()
  })

  it('updates token input on change', () => {
    render(
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    )
    
    const input = screen.getByLabelText('Admin Token') as HTMLInputElement
    fireEvent.change(input, { target: { value: 'test-token' } })
    
    expect(input.value).toBe('test-token')
  })
})
