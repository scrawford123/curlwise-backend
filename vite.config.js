import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc"; // Use SWC plugin for React

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
});
