import axios from "axios";
import { clientConfig } from "./client-config";

const api = axios.create({
  baseURL: clientConfig.apiUrl,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.response.use(
  (response) => {
    if (response.data && "success" in response.data && !response.data.success) {
      return Promise.reject(new Error(response.data.error || "Request failed"));
    }
    return response;
  },
  (error) => {
    const message =
      error.response?.data?.error ||
      error.response?.data?.detail ||
      error.message ||
      "An unexpected error occurred";

    return Promise.reject(new Error(message));
  }
);

export default api;
