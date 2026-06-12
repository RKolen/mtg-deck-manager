<?php

/**
 * @file
 * MTG project settings — CORS origins from DRUPAL_CORS_ORIGINS env var.
 */

declare(strict_types=1);

$raw = getenv('DRUPAL_CORS_ORIGINS');
if (!is_string($raw) || $raw === '') {
  return;
}

$origins = array_values(array_filter(array_map('trim', explode(',', $raw))));
if ($origins === []) {
  return;
}

$lines = [
  'parameters:',
  '  cors.config:',
  '    enabled: true',
  "    allowedHeaders: ['Content-Type', 'Accept', 'Authorization', 'X-CSRF-Token']",
  "    allowedMethods: ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS']",
  '    allowedOrigins:',
];
foreach ($origins as $origin) {
  $lines[] = "      - '" . str_replace("'", "''", $origin) . "'";
}
$lines = array_merge($lines, [
  '    allowedOriginsPatterns: []',
  '    exposedHeaders: false',
  '    maxAge: 600',
  '    supportsCredentials: false',
  '',
]);

$cors_file = __DIR__ . '/services.cors.env.yml';
file_put_contents($cors_file, implode("\n", $lines));
$settings['container_yamls'][] = $cors_file;
