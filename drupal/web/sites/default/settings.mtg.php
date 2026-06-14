<?php

/**
 * @file
 * MTG project settings — sidecar Ollama routing and CORS from env vars.
 */

declare(strict_types=1);

// Ollama connection is env-only (MTG_AI_SIDECAR_URL). Do not export host/port to config sync.
$settings['config_export_blacklist'] = array_values(array_unique(array_merge(
  $settings['config_export_blacklist'] ?? [],
  ['ai_provider_ollama.settings'],
)));

// Ollama host/port are not stored in config sync — they come from MTG_AI_SIDECAR_URL
// (see drupal/.ddev/config.local.yaml web_environment).
$sidecar = getenv('MTG_AI_SIDECAR_URL');
if (is_string($sidecar) && $sidecar !== '') {
  $parsed = parse_url($sidecar);
  if (is_array($parsed) && isset($parsed['host'])) {
    $scheme = $parsed['scheme'] ?? 'http';
    $config['ai_provider_ollama.settings']['host_name'] = $scheme . '://' . $parsed['host'];
    if (!empty($parsed['port'])) {
      $config['ai_provider_ollama.settings']['port'] = (int) $parsed['port'];
    }
  }
}

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
