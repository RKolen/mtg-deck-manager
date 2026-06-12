import { GraphQLClient } from 'graphql-request';

let _client: GraphQLClient | null = null;

/**
 * Singleton GraphQL client for Drupal GraphQL Compose + MTG schema extension.
 * All entity reads and mutations use {NEXT_PUBLIC_DRUPAL_URL}/graphql.
 */
export function getGraphQLClient(): GraphQLClient {
  if (_client !== null) {
    return _client;
  }

  const url = process.env.NEXT_PUBLIC_DRUPAL_URL;
  const user = process.env.NEXT_PUBLIC_DRUPAL_USER;
  const pass = process.env.NEXT_PUBLIC_DRUPAL_PASS;

  if (!url || !user || !pass) {
    throw new Error(
      'Missing required environment variables: ' +
        'NEXT_PUBLIC_DRUPAL_URL, NEXT_PUBLIC_DRUPAL_USER, NEXT_PUBLIC_DRUPAL_PASS',
    );
  }

  _client = new GraphQLClient(`${url}/graphql`, {
    headers: {
      Authorization: `Basic ${btoa(`${user}:${pass}`)}`,
    },
  });
  return _client;
}
