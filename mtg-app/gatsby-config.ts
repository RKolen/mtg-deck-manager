import type { GatsbyConfig } from 'gatsby';

const config: GatsbyConfig = {
  siteMetadata: {
    title: 'MTG Deck Manager',
    siteUrl: process.env.SITE_URL,
  },
  plugins: ['gatsby-plugin-typescript'],
};

export default config;
