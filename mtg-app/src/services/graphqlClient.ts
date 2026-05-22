import { GraphQLClient } from 'graphql-request';

let _composeClient: GraphQLClient | null = null;
let _mtgClient: GraphQLClient | null = null;

function createClient(path: string): GraphQLClient {
  const url = process.env.GATSBY_DRUPAL_URL;
  const user = process.env.GATSBY_DRUPAL_USER;
  const pass = process.env.GATSBY_DRUPAL_PASS;

  if (!url || !user || !pass) {
    throw new Error(
      'Missing required environment variables: ' +
        'GATSBY_DRUPAL_URL, GATSBY_DRUPAL_USER, GATSBY_DRUPAL_PASS',
    );
  }

  return new GraphQLClient(`${url}${path}`, {
    headers: {
      Authorization: `Basic ${btoa(`${user}:${pass}`)}`,
    },
  });
}

/**
 * GraphQL Compose schema — entity reads (decks, cards, collection, etc.).
 */
export function getGraphQLClient(): GraphQLClient {
  if (_composeClient === null) {
    _composeClient = createClient('/graphql');
  }
  return _composeClient;
}

/**
 * Custom MTG schema — mutations and queries not yet exposed via Compose
 * (filtered card search, deck card paragraphs, collection value, etc.).
 */
export function getMtgGraphQLClient(): GraphQLClient {
  if (_mtgClient === null) {
    _mtgClient = createClient('/graphql/mtg');
  }
  return _mtgClient;
}
