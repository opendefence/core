// Built by themePlugin in vite.config.ts from public/themes/<VITE_THEME>
declare module "virtual-theme-config" {
  const theme: {
    id: string;
    name: string;
    short_name?: string;
    description?: string;
    variables: import("./theme").ThemeVariables;
    metadata: import("./theme").ThemeMetadata;
    localization: Record<string, Record<string, unknown>>;
    baseUrl: string;
  };
  export default theme;
}
