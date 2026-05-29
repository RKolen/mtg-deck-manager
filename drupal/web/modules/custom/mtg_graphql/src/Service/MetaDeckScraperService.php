<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;

/**
 * Scrapes MTGGoldfish metagame pages and upserts meta_deck nodes.
 *
 * Upsert semantics:
 *  - New archetype  → create a new meta_deck node.
 *  - Existing match → update field_cards_json, field_meta_share,
 *                     field_fetched_at, and field_archetype_tags only.
 *  - Fallen-out-of-meta decks are never deleted.
 */
final class MetaDeckScraperService {

  private const USER_AGENT = 'MTG Deck Manager (personal project, non-commercial)';

  /**
   * Base URL for MTGGoldfish, configurable via MTGGOLDFISH_BASE_URL env var.
   */
  private string $mtggoldfishBase;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly ClientInterface $httpClient,
  ) {
    $env = getenv('MTGGOLDFISH_BASE_URL');
    if (!is_string($env) || $env === '') {
      throw new \RuntimeException('MTGGOLDFISH_BASE_URL environment variable is not set.');
    }
    $this->mtggoldfishBase = $env;
  }

  /**
   * Scrapes the given format and upserts meta_deck nodes.
   *
   * @param string $formatName
   *   The display name of the format, e.g. "Pioneer". Must match a taxonomy
   *   term in the mtg_format vocabulary.
   * @param int $limit
   *   Maximum number of archetypes to import.
   *
   * @return array{format: string, created: int, updated: int, skipped: int}
   *   Counts of nodes created, updated, and skipped due to fetch errors.
   *
   * @throws \InvalidArgumentException
   *   When no mtg_format term exists for the given format name.
   */
  public function scrape(string $formatName, int $limit = 20): array {
    $slug = $this->resolveSlug($formatName);

    $result = [
      'format'  => $formatName,
      'created' => 0,
      'updated' => 0,
      'skipped' => 0,
    ];

    try {
      $metagameHtml = $this->get($this->mtggoldfishBase . '/metagame/' . $slug . '#paper');
    }
    catch (GuzzleException $e) {
      throw new \RuntimeException('Failed to fetch metagame page: ' . $e->getMessage(), 0, $e);
    }

    $archetypes = $this->parseArchetypes($metagameHtml, $limit);

    foreach ($archetypes as $arch) {
      try {
        $deckHtml = $this->get($arch['url']);
        $cards    = $this->parseDecklist($deckHtml);
        $tags     = $this->inferTags($deckHtml);
        usleep(1_000_000);
      }
      catch (GuzzleException $e) {
        $result['skipped']++;
        continue;
      }

      $action = $this->upsertNode($arch['name'], $formatName, $arch['share'], $cards, $tags);
      if ($action === 'created') {
        $result['created']++;
      }
      else {
        $result['updated']++;
      }
    }

    return $result;
  }

  /**
   * Performs a GET request and returns the response body as a string.
   *
   * @throws \GuzzleHttp\Exception\GuzzleException
   */
  private function get(string $url): string {
    $response = $this->httpClient->request('GET', $url, [
      'headers' => ['User-Agent' => self::USER_AGENT],
      'timeout' => 30,
      'verify'  => FALSE,
    ]);
    return (string) $response->getBody();
  }

  /**
   * Extracts archetype name, meta share, and deck URL from a metagame page.
   *
   * @return list<array{name: string, share: float, url: string}>
   *   List of archetypes with name, meta share percentage and full deck URL.
   */
  private function parseArchetypes(string $html, int $limit): array {
    // Find all #paper archetype links; each archetype appears multiple times
    // (paper / online / base). We use the canonical (non-#paper) href to
    // deduplicate and build the deck URL.
    $pattern = '/<a\s[^>]*href="(\/archetype\/[^"]+?)"[^>]*>([^<]{3,80})<\/a>/i';
    preg_match_all($pattern, $html, $matches, PREG_SET_ORDER);

    $archetypes = [];
    $seen       = [];

    foreach ($matches as $m) {
      $href = $m[1];
      if (!str_ends_with($href, '#paper')) {
        continue;
      }
      $canonical = str_replace('#paper', '', $href);
      if (isset($seen[$canonical])) {
        continue;
      }
      $seen[$canonical] = TRUE;

      $name = html_entity_decode(trim(strip_tags($m[2])), ENT_QUOTES | ENT_HTML5, 'UTF-8');
      if ($name === '') {
        continue;
      }

      $share = $this->extractShareNear($html, $href);

      $archetypes[] = [
        'name'  => $name,
        'share' => $share,
        'url'   => $this->mtggoldfishBase . $canonical,
      ];

      if (count($archetypes) >= $limit) {
        break;
      }
    }

    return $archetypes;
  }

  /**
   * Extracts the nearest percentage value to an archetype link in the HTML.
   */
  private function extractShareNear(string $html, string $href): float {
    $pos = strpos($html, $href);
    if ($pos === FALSE) {
      return 0.0;
    }
    $window = substr($html, max(0, $pos - 500), 1200);
    if (preg_match('/(\d+\.?\d*)\s*%/', $window, $pct)) {
      return (float) $pct[1];
    }
    return 0.0;
  }

  /**
   * Parses the plain-text decklist embedded in an archetype page.
   *
   * MTGGoldfish embeds lines like "4 Lightning Bolt" in the raw HTML.
   * A "sideboard" line in the source marks the transition to sideboard cards.
   *
   * @return list<array{name: string, quantity: int, sideboard: bool}>
   *   List of card entries with name, quantity and sideboard flag.
   */
  private function parseDecklist(string $html): array {
    $cards     = [];
    $sideboard = FALSE;

    foreach (explode("\n", $html) as $raw) {
      $line = trim(html_entity_decode($raw, ENT_QUOTES | ENT_HTML5, 'UTF-8'));

      if (strtolower($line) === 'sideboard') {
        $sideboard = TRUE;
        continue;
      }
      if (preg_match('/^(\d{1,2})\s+(.+)$/', $line, $m)) {
        $cards[] = [
          'name'      => trim($m[2]),
          'quantity'  => (int) $m[1],
          'sideboard' => $sideboard,
        ];
      }
    }

    return $cards;
  }

  /**
   * Infers strategy tags from page text using keyword matching.
   *
   * @return list<string>
   *   Strategy tag strings, e.g. 'aggro', 'control', 'combo'.
   */
  private function inferTags(string $html): array {
    $text = strtolower(strip_tags($html));
    $tags = [];

    if (str_contains($text, 'aggro') || str_contains($text, 'aggressive')) {
      $tags[] = 'aggro';
    }
    if (str_contains($text, 'midrange') || str_contains($text, 'mid-range')) {
      $tags[] = 'midrange';
    }
    if (str_contains($text, 'control') || str_contains($text, 'counterspell')) {
      $tags[] = 'control';
    }
    if (str_contains($text, 'combo') || str_contains($text, 'infinite') || str_contains($text, 'storm')) {
      $tags[] = 'combo';
    }
    if (str_contains($text, 'tempo')) {
      $tags[] = 'tempo';
    }
    if (str_contains($text, 'ramp') || str_contains($text, 'big mana')) {
      $tags[] = 'ramp';
    }
    if ($tags === []) {
      $tags[] = 'midrange';
    }

    return array_values(array_unique($tags));
  }

  /**
   * Creates or updates a meta_deck node.
   *
   * @param string $archetypeName
   *   The archetype display name used as the node title.
   * @param string $formatName
   *   The format display name stored in field_format.
   * @param float $metaShare
   *   The metagame share percentage for this archetype.
   * @param list<array{name: string, quantity: int, sideboard: bool}> $cards
   *   Parsed decklist entries.
   * @param list<string> $tags
   *   Strategy tags to store on the node.
   *
   * @return string
   *   Either 'created' for new nodes or 'updated' for existing nodes.
   */
  private function upsertNode(
    string $archetypeName,
    string $formatName,
    float $metaShare,
    array $cards,
    array $tags,
  ): string {
    $storage   = $this->entityTypeManager->getStorage('node');
    $fetchedAt = gmdate('Y-m-d\TH:i:s');
    $cardsJson = json_encode($cards, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);

    $existing = $storage->loadByProperties([
      'type'         => 'meta_deck',
      'title'        => $archetypeName,
      'field_format' => $formatName,
    ]);
    $node = reset($existing);

    if ($node !== FALSE) {
      // Update only the fields that change with a new scrape run.
      $node->set('field_cards_json', $cardsJson);
      $node->set('field_meta_share', round($metaShare, 2));
      $node->set('field_fetched_at', $fetchedAt);
      $node->set('field_archetype_tags', array_map(
        static fn(string $t): array => ['value' => $t],
        $tags,
      ));
      $node->setNewRevision(FALSE);
      $node->save();
      return 'updated';
    }

    // Build tag items for the multi-value string field.
    $tagItems = array_map(
      static fn(string $t): array => ['value' => $t],
      $tags,
    );

    $newNode = $storage->create([
      'type'                => 'meta_deck',
      'title'               => $archetypeName,
      'status'              => 1,
      'field_format'        => $formatName,
      'field_meta_share'    => round($metaShare, 2),
      'field_cards_json'    => $cardsJson,
      'field_archetype_tags' => $tagItems,
      'field_fetched_at'    => $fetchedAt,
    ]);
    $newNode->save();
    return 'created';
  }

  /**
   * Resolves a format display name to its MTGGoldfish slug via taxonomy.
   *
   * @throws \InvalidArgumentException
   *   When no matching mtg_format term is found.
   */
  private function resolveSlug(string $formatName): string {
    $terms = $this->entityTypeManager
      ->getStorage('taxonomy_term')
      ->loadByProperties(['vid' => 'mtg_format', 'name' => $formatName]);

    $term = reset($terms);
    if ($term === FALSE) {
      throw new \InvalidArgumentException(
        'Unknown format "' . $formatName . '". Add it to the mtg_format taxonomy.'
      );
    }

    $slug = $term->get('field_goldfish_slug')->value;
    if (!is_string($slug) || $slug === '') {
      throw new \InvalidArgumentException(
        'Format "' . $formatName . '" has no field_goldfish_slug value.'
      );
    }

    return $slug;
  }

}
