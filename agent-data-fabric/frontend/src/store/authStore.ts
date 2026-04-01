import { create } from 'zustand';
import type { User } from '../types';
import { authApi } from '../api/client';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('adf_token'),
  isAuthenticated: !!localStorage.getItem('adf_token'),
  isLoading: false,

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const res = await authApi.login(email, password);
      const { access_token, refresh_token } = res.data;
      localStorage.setItem('adf_token', access_token);
      localStorage.setItem('adf_refresh_token', refresh_token);
      set({ token: access_token, isAuthenticated: true, isLoading: false });

      const userRes = await authApi.me();
      set({ user: userRes.data });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('adf_token');
    localStorage.removeItem('adf_refresh_token');
    set({ user: null, token: null, isAuthenticated: false });
  },

  loadUser: async () => {
    try {
      const res = await authApi.me();
      set({ user: res.data, isAuthenticated: true });
    } catch {
      set({ user: null, isAuthenticated: false });
    }
  },
}));
