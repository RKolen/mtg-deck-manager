import { GraphQLClient } from 'graphql-request';

let _client: GraphQLClient | null = null;

/**
 * Returns a singleton GraphQLClient pointed at the Drupal GraphQL endpoint.
 * Lazy-initialised on first call so the module is safe to import during
 * Gatsby's SSR build phase (where process.env.GATSBY_* vars and btoa are
 * not needed until actual browser-side queries run).
 */
export function getGraphQLClient(): GraphQLClient {
  if (_client !== null) return _client;

  const url  = process.env.GATSBY_DRUPAL_URL;
  const user = process.env.GATSBY_DRUPAL_USER;
  const pass = process.env.GATSBY_DRUPAL_PASS;

  if (!url || !user || !pass) {
    throw new Error(
      'Missing required environment variables: ' +
        'GATSBY_DRUPAL_URL, GATSBY_DRUPAL_USER, GATSBY_DRUPAL_PASS',
    );
  }

  _client = new GraphQLClient(`${url}/graphql`, {
    headers: {
      Authorization: `Basic ${btoa(`${user}:${pass}`)}`,
    },
  });
  return _client;
}
