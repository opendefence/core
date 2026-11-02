import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "fi.opendefence.core",
  appName: "OpenDefence",
  webDir: "dist",
  android: {
    allowMixedContent: false,
  },
  plugins: {
    // Native HTTP skips CORS from https://localhost
    CapacitorHttp: { enabled: true },
  },
};

export default config;
