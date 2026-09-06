import { defineStore } from "pinia";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: "" as string,
  }),
  actions: {
    hydrate() {
      if (import.meta.client) {
        this.token = localStorage.getItem("shnpp_token") || "";
      }
    },
    setToken(token: string) {
      this.token = token;
      localStorage.setItem("shnpp_token", token);
    },
    logout() {
      this.token = "";
      localStorage.removeItem("shnpp_token");
      navigateTo("/");
    },
  },
});
