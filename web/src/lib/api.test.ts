import { describe, it, expect, vi, beforeEach } from 'vitest'
import api, { dashboardApi, studentsApi, conversationsApi, rulesApi, promptsApi } from './api'

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('dashboardApi', () => {
    it('should have getStats method', () => {
      expect(typeof dashboardApi.getStats).toBe('function')
    })

    it('should have getActivity method', () => {
      expect(typeof dashboardApi.getActivity).toBe('function')
    })
  })

  it('redirects to login under BASE_URL on 401', async () => {
    // In production this app is served under `/TeachProxy/` (nginx + Vite base).
    // We derive the redirect target from the current path to avoid hardcoding.
    window.location.pathname = '/TeachProxy/students'
    const expectedHref = '/TeachProxy/login'
    window.location.href = ''

    const handler = api.interceptors.response.handlers.find((h) => typeof h?.rejected === 'function')
    expect(handler).toBeTruthy()

    try {
      await handler!.rejected!({ response: { status: 401 } })
    } catch {
      // axios interceptor is expected to reject
    }

    expect(window.location.href).toBe(expectedHref)
  })

  describe('studentsApi', () => {
    it('should have all CRUD methods', () => {
      expect(typeof studentsApi.list).toBe('function')
      expect(typeof studentsApi.create).toBe('function')
      expect(typeof studentsApi.updateQuota).toBe('function')
      expect(typeof studentsApi.resetQuota).toBe('function')
      expect(typeof studentsApi.regenerateKey).toBe('function')
      expect(typeof studentsApi.delete).toBe('function')
    })
  })

  describe('conversationsApi', () => {
    it('should have list method', () => {
      expect(typeof conversationsApi.list).toBe('function')
    })
  })

  describe('rulesApi', () => {
    it('should have all CRUD methods', () => {
      expect(typeof rulesApi.list).toBe('function')
      expect(typeof rulesApi.create).toBe('function')
      expect(typeof rulesApi.update).toBe('function')
      expect(typeof rulesApi.delete).toBe('function')
      expect(typeof rulesApi.toggle).toBe('function')
      expect(typeof rulesApi.reloadCache).toBe('function')
    })
  })

  describe('promptsApi', () => {
    it('should have all CRUD methods', () => {
      expect(typeof promptsApi.list).toBe('function')
      expect(typeof promptsApi.getCurrent).toBe('function')
      expect(typeof promptsApi.create).toBe('function')
      expect(typeof promptsApi.delete).toBe('function')
    })
  })
})
