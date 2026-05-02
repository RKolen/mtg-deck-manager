/**
 * Shared Axios factory for all Drupal backend clients.
 *
 * Reads connection details from environment variables and throws immediately
 * if any are missing, so misconfiguration surfaces at startup rather than
 * silently producing requests with empty credentials.
 */

import axios, { type AxiosInstance } from 'axios';

/**
 * Creates an Axios instance pre-configured with the Drupal base URL and
 * Basic Auth credentials sourced from environment variables.
 *
 * @param basePath     - Path appended to GATSBY_DRUPAL_URL (e.g. '/jsonapi').
 * @param extraHeaders - Additional headers merged into every request.
 */
export function createDrupalClient(
  basePath: string,
  extraHeaders: Record<string, string> = {},
): AxiosInstance {
  const url = process.env.GATSBY_DRUPAL_URL;
  const user = process.env.GATSBY_DRUPAL_USER;
  const pass = process.env.GATSBY_DRUPAL_PASS;

  if (!url || !user || !pass) {
    throw new Error(
      'Missing required environment variables: ' +
        'GATSBY_DRUPAL_URL, GATSBY_DRUPAL_USER, GATSBY_DRUPAL_PASS',
    );
  }

  return axios.create({
    baseURL: `${url}${basePath}`,
    auth: { username: user, password: pass },
    headers: extraHeaders,
  });
}
