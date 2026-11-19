<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql;

/**
 * Two-commander pairing rules, read from oracle text and type lines.
 *
 * Covers Partner, Partner with <name>, Partner—<variant>, Friends forever,
 * Choose a Background and Doctor's companion.
 */
final class PartnerRules {

  /**
   * Pairing abilities of a card.
   *
   * @param string $name
   *   Card name (title).
   * @param string $typeLine
   *   Type line.
   * @param string $oracle
   *   Oracle text.
   *
   * @return array{partner: bool, with: ?string, variant: ?string, friends: bool, chooseBackground: bool, background: bool, companion: bool, doctor: bool}
   *   What the card can pair with.
   */
  public static function abilities(string $name, string $typeLine, string $oracle): array {
    $with = NULL;
    $variant = NULL;
    $partner = FALSE;
    foreach (preg_split('/\R/', $oracle) ?: [] as $line) {
      $line = trim($line);
      if (preg_match('/^Partner with ([^(]+?)\s*(?:\(|$)/u', $line, $m)) {
        $with = trim($m[1]);
      }
      elseif (preg_match('/^Partner\s*(?:—|–|-)\s*([^(]+?)\s*(?:\(|$)/u', $line, $m)) {
        $variant = trim($m[1]);
      }
      elseif (preg_match('/^Partner\s*(?:\(|$)/u', $line)) {
        $partner = TRUE;
      }
    }
    return [
      'partner' => $partner,
      'with' => $with,
      'variant' => $variant,
      'friends' => (bool) preg_match('/^Friends forever\b/mu', $oracle),
      'chooseBackground' => (bool) preg_match('/^Choose a Background\b/mu', $oracle),
      'background' => str_contains($typeLine, 'Background'),
      'companion' => (bool) preg_match('/^Doctor\'s companion\b/mu', $oracle),
      'doctor' => (bool) preg_match('/\bTime Lord\b.*\bDoctor\b/u', $typeLine),
    ];
  }

  /**
   * Whether a commander may have a second commander at all.
   */
  public static function allowsPartner(string $name, string $typeLine, string $oracle): bool {
    $a = self::abilities($name, $typeLine, $oracle);
    return $a['partner'] || $a['with'] !== NULL || $a['variant'] !== NULL || $a['friends']
      || $a['chooseBackground'] || $a['companion'] || $a['doctor'];
  }

  /**
   * Whether two cards can be commanders together.
   *
   * @param array{name: string, typeLine: string, oracle: string} $first
   *   The commander.
   * @param array{name: string, typeLine: string, oracle: string} $second
   *   The proposed partner.
   */
  public static function canPair(array $first, array $second): bool {
    if ($first['name'] === $second['name']) {
      return FALSE;
    }
    $a = self::abilities($first['name'], $first['typeLine'], $first['oracle']);
    $b = self::abilities($second['name'], $second['typeLine'], $second['oracle']);
    if ($a['partner'] && $b['partner']) {
      return TRUE;
    }
    if ($a['with'] !== NULL && $b['with'] !== NULL
      && self::sameName($a['with'], $second['name']) && self::sameName($b['with'], $first['name'])) {
      return TRUE;
    }
    if ($a['variant'] !== NULL && $a['variant'] === $b['variant']) {
      return TRUE;
    }
    if ($a['friends'] && $b['friends']) {
      return TRUE;
    }
    if (($a['chooseBackground'] && $b['background']) || ($b['chooseBackground'] && $a['background'])) {
      return TRUE;
    }
    return ($a['companion'] && $b['doctor']) || ($b['companion'] && $a['doctor']);
  }

  /**
   * Name match that ignores case and the back face of a double-faced title.
   */
  private static function sameName(string $named, string $title): bool {
    $front = trim(explode(' // ', $title)[0]);
    return strcasecmp(trim($named), $front) === 0 || strcasecmp(trim($named), $title) === 0;
  }

}
