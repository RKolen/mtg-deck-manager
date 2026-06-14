<?php

declare(strict_types=1);

namespace Drupal\mtg_card_suggestions\Support;

/**
 * Resolves the host-side AI sidecar URL for Drupal → Ollama calls.
 */
final class SidecarUrl {

  /**
   * Return the sidecar /api/chat endpoint, or NULL when not configured.
   */
  public static function chatEndpoint(): ?string {
    $sidecar = getenv('MTG_AI_SIDECAR_URL');
    if ($sidecar === FALSE || $sidecar === '') {
      return NULL;
    }
    return rtrim($sidecar, '/') . '/api/chat';
  }

}
