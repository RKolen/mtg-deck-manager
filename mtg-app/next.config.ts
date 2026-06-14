import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_DRUPAL_URL: process.env.NEXT_PUBLIC_DRUPAL_URL ?? process.env.GATSBY_DRUPAL_URL,
    NEXT_PUBLIC_DRUPAL_USER: process.env.NEXT_PUBLIC_DRUPAL_USER ?? process.env.GATSBY_DRUPAL_USER,
    NEXT_PUBLIC_DRUPAL_PASS: process.env.NEXT_PUBLIC_DRUPAL_PASS ?? process.env.GATSBY_DRUPAL_PASS,
    NEXT_PUBLIC_SIM_URL: process.env.NEXT_PUBLIC_SIM_URL ?? process.env.GATSBY_SIM_URL,
    NEXT_PUBLIC_CLASSIFIER_URL:
      process.env.NEXT_PUBLIC_CLASSIFIER_URL ?? process.env.GATSBY_CLASSIFIER_URL,
  },
};

export default nextConfig;
