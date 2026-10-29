// The platform serves two origins: the base domain for enrollment, app.<domain> for mTLS.
const APP_LABEL = "app";

export function isAppOrigin(): boolean {
  return window.location.hostname.startsWith(`${APP_LABEL}.`);
}

export function appUrl(domain: string): string {
  return originUrl(`${APP_LABEL}.${domain}`);
}

export function baseUrl(domain: string): string {
  return originUrl(domain);
}

function originUrl(host: string): string {
  const { protocol, port } = window.location;
  return `${protocol}//${host}${port ? `:${port}` : ""}/`;
}
