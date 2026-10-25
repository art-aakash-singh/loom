/** The only place `import.meta.env` is read; everything else imports from here. */
export const env = {
  apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
} as const;
