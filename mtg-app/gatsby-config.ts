import type { GatsbyConfig } from 'gatsby';

const DRUPAL_URL = process.env.DRUPAL_URL ?? 'https://mtg-deck-manager.ddev.site';

const config: GatsbyConfig = {
  siteMetadata: {
    title: 'MTG Deck Manager',
    siteUrl: 'http://localhost:8000',
  },
  plugins: [
    {
      resolve: 'gatsby-source-drupal',
      options: {
        baseUrl: DRUPAL_URL,
        // Only fetch basic_page nodes for CMS-driven static pages (home page).
        // All card, deck, and collection data is fetched at runtime via JSON:API.
        filters: {
          'node--page': 'filter[status][value]=1',
        },
        // Exclude the large content types entirely — Drupal's MAX_SIZE=50 cap
        // makes fetching 108k mtg_card nodes impractical at build time.
        disallowedLinkTypes: [
          'node--mtg_card',
          'node--deck',
          'node--deck_card',
          'node--collection_card',
        ],
      },
    },
  ],
};

export default config;
