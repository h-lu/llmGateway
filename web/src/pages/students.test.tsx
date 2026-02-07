import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { StudentsPage } from './students'

const { mockStudentsApi, mockConversationsApi } = vi.hoisted(() => ({
  mockStudentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    updateQuota: vi.fn(),
    resetQuota: vi.fn(),
    regenerateKey: vi.fn(),
    delete: vi.fn(),
    getStats: vi.fn(),
  },
  mockConversationsApi: {
    list: vi.fn(),
    getByStudent: vi.fn(),
    search: vi.fn(),
  },
}))

vi.mock('@/lib/api', () => ({
  studentsApi: mockStudentsApi,
  conversationsApi: mockConversationsApi,
}))

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('StudentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows an error message when creating a student fails', async () => {
    mockStudentsApi.list.mockResolvedValue([])
    mockStudentsApi.create.mockRejectedValue({
      response: { status: 409, data: { detail: 'Email already registered' } },
    })

    renderWithQuery(<StudentsPage />)

    const addButton = await screen.findByRole('button', { name: /add student/i })
    fireEvent.click(addButton)

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'Alice' } })
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'alice@example.com' } })
    fireEvent.click(screen.getByRole('button', { name: /^create$/i }))

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toMatch(/email already registered/i)
  })
})
