import { defineStore } from 'pinia';

const ACCESS_TOKEN_KEY = 'admin_access_token';
const LOGIN_USER_KEY = 'admin_login_user';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: localStorage.getItem(ACCESS_TOKEN_KEY) ?? '',
    username: localStorage.getItem(LOGIN_USER_KEY) ?? ''
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken)
  },
  actions: {
    login(username: string, token: string) {
      this.username = username;
      this.accessToken = token;
      localStorage.setItem(ACCESS_TOKEN_KEY, token);
      localStorage.setItem(LOGIN_USER_KEY, username);
    },
    logout() {
      this.username = '';
      this.accessToken = '';
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(LOGIN_USER_KEY);
    }
  }
});
