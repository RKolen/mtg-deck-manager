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
        // Pull mtg_card for build-time card browsing and basic_page for
        // CMS-driven static pages (e.g. the home page).
        // Decks, collection, and analysis data are fetched client-side.
        filters: {
          'node--mtg_card': 'filter[status][value]=1',
          'node--page': 'filter[status][value]=1',
        },
      },
    },
  ],
};

export default config;
