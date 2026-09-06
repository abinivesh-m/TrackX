// frontend/src/services/auth.ts

import { api } from './api'
import type { User } from '@/types'

const ACCESS_TOKEN_KEY = 'trackx_access_token'
const REFRESH_TOKEN_KEY = 'trackx_refresh_token'
const USER_KEY = 'trackx_user'

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export const authService = {
  async login(username: string, password: string): Promise<void> {
    const formData = new FormData()
    formData.append('username', username)
    formData.append('password', password)
    
    const response = await api.post<LoginResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
    
    this.setTokens(response.access_token, response.refresh_token)
    const user = await api.get<User>('/auth/me')
    this.setUser(user)
  },

  async register(data: { username: string; email: string; password: string; full_name?: string }): Promise<void> {
    await api.post('/auth/register', data)
  },

  async logout(): Promise<void> {
    localStorage.removeItem(ACCESS_TOKEN_KEY)
    localStorage.removeItem(REFRESH_TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    window.location.href = '/login'
  },

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY)
  },

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY)
  },

  setTokens(accessToken: string, refreshToken: string): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
  },

  setUser(user: any): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },

  getUser(): any | null {
    const user = localStorage.getItem(USER_KEY)
    return user ? JSON.parse(user) : null
  },

  isAuthenticated(): boolean {
    return !!this.getAccessToken()
  },

  async changePassword(username: string, oldPassword: string, newPassword: string): Promise<void> {
    await api.post('/auth/change-password', { username, old_password: oldPassword, new_password: newPassword })
  },

  async refreshToken(): Promise<LoginResponse> {
    const refreshToken = this.getRefreshToken()
    if (!refreshToken) {
      throw new Error('No refresh token available')
    }
    
    const response = await api.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken })
    this.setTokens(response.access_token, response.refresh_token)
    const user = await api.get<User>('/auth/me')
    this.setUser(user)
    return response
  }
}
