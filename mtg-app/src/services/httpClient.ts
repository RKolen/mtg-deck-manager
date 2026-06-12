/**
 * Shared Axios factory for all Drupal backend clients.
 *
 * Credentials are resolved on the first request so Next.js builds do not
 * require runtime environment variables at module load time.
 */

import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

function applyDrupalAuth(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  const url = process.env.NEXT_PUBLIC_DRUPAL_URL;
  const user = process.env.NEXT_PUBLIC_DRUPAL_USER;
  const pass = process.env.NEXT_PUBLIC_DRUPAL_PASS;

  if (!url || !user || !pass) {
    throw new Error(
      'Missing required environment variables: ' +
        'NEXT_PUBLIC_DRUPAL_URL, NEXT_PUBLIC_DRUPAL_USER, NEXT_PUBLIC_DRUPAL_PASS',
    );
  }

  config.auth = { username: user, password: pass };
  if (config.baseURL != null && !config.baseURL.startsWith('http')) {
    config.baseURL = `${url}${config.baseURL}`;
  }
  return config;
}

/**
 * Creates an Axios instance pre-configured with the Drupal base URL and
 * Basic Auth credentials sourced from environment variables.
 *
 * @param basePath     - Path appended to NEXT_PUBLIC_DRUPAL_URL (e.g. '/api').
 * @param extraHeaders - Additional headers merged into every request.
 */
export function createDrupalClient(
  basePath: string,
  extraHeaders: Record<string, string> = {},
): AxiosInstance {
  const instance = axios.create({
    baseURL: basePath,
    headers: extraHeaders,
  });
  instance.interceptors.request.use(applyDrupalAuth);
  return instance;
}
