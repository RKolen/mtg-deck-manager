<?php

declare(strict_types=1);

namespace Drupal\mtg_graphql\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Database\Query\SelectInterface;
use Drupal\Core\Database\Statement\FetchAs;

/**
 * Reads the whole collection with single SQL queries.
 *
 * Loading 2,000+ collection rows and their cards as entities, 100 per
 * GraphQL page, takes many seconds; these flat queries take milliseconds.
 */
final class CollectionReader {

  /**
   * Card fields returned with each row, keyed by result alias.
   */
  private const CARD_FIELDS = [
    'setCode' => 'field_set_code',
    'setName' => 'field_set_name',
    'collectorNumber' => 'field_collector_number',
    'typeLine' => 'field_type_line',
    'cmc' => 'field_cmc',
    'priceUsd' => 'field_price_usd',
    'priceUsdFoil' => 'field_price_usd_foil',
    'priceEur' => 'field_price_eur',
    'priceEurFoil' => 'field_price_eur_foil',
    'imageUri' => 'field_image_uri',
    'fullArt' => 'field_full_art',
    'borderColor' => 'field_border_color',
  ];

  public function __construct(
    private readonly Connection $database,
  ) {}

  /**
   * Every collection row with its card's display fields.
   *
   * @return array<int, array<string, mixed>>
   *   Flat rows keyed like the CollectionRow GraphQL type.
   */
  public function rows(): array {
    $query = $this->baseQuery();
    $query->condition('cc.status', 1);
    $query->addField('o', 'field_quantity_owned_value', 'quantityOwned');
    $query->addField('f', 'field_quantity_foil_value', 'quantityFoil');
    $query->join('node', 'ccn', 'ccn.nid = cc.nid');
    $query->addField('ccn', 'uuid', 'id');
    $query->addField('c', 'uuid', 'cardId');
    $query->addField('cd', 'title', 'title');
    $query->addField('t', 'field_quantity_trade_value', 'quantityTrade');
    $query->addField('b', 'field_binder_location_value', 'binderLocation');
    $query->leftJoin('node__field_quantity_trade', 't', 't.entity_id = cc.nid');
    $query->leftJoin('node__field_binder_location', 'b', 'b.entity_id = cc.nid');
    foreach (self::CARD_FIELDS as $alias => $field) {
      $table = 'x_' . $alias;
      $query->leftJoin("node__$field", $table, "$table.entity_id = c.nid");
      $query->addField($table, $field . '_value', $alias);
    }
    $query->orderBy('cd.title');

    $rows = [];
    foreach ($query->execute()->fetchAll(FetchAs::Associative) as $row) {
      $row['quantityOwned'] = (int) ($row['quantityOwned'] ?? 0);
      $row['quantityFoil'] = (int) ($row['quantityFoil'] ?? 0);
      $row['quantityTrade'] = (int) ($row['quantityTrade'] ?? 0);
      $row['cmc'] = $row['cmc'] === NULL ? NULL : (float) $row['cmc'];
      $row['fullArt'] = (bool) $row['fullArt'];
      $rows[] = $row;
    }
    return $rows;
  }

  /**
   * Collection value in one currency, published rows only.
   *
   * Regular copies take the regular price, then foil, then the same in the
   * other currency converted; foil copies the same with foil first. This
   * matches MtgGraphqlResolverRegistration::bestPrice().
   *
   * @param bool $eur
   *   TRUE for EUR, FALSE for USD.
   * @param float $usdToEur
   *   Euros per US dollar, for prices only listed in the other currency.
   */
  public function value(bool $eur, float $usdToEur): float {
    [$cur, $oth] = $eur ? ['eur', 'usd'] : ['usd', 'eur'];
    $factor = $eur ? $usdToEur : 1 / $usdToEur;
    $query = $this->baseQuery();
    $query->condition('cc.status', 1);
    foreach (["{$cur}", "{$cur}_foil", "{$oth}", "{$oth}_foil"] as $key) {
      $query->leftJoin("node__field_price_$key", "p_$key", "p_$key.entity_id = c.nid");
    }
    $price = fn(string $key): string => "NULLIF(p_$key.field_price_{$key}_value, 0)";
    $converted = fn(string $key): string => "{$price($key)} * :factor";
    $regular = "COALESCE({$price($cur)}, {$price("{$cur}_foil")}, {$converted($oth)}, {$converted("{$oth}_foil")}, 0)";
    $foil = "COALESCE({$price("{$cur}_foil")}, {$price($cur)}, {$converted("{$oth}_foil")}, {$converted($oth)}, 0)";
    $query->addExpression(
      "SUM($regular * COALESCE(o.field_quantity_owned_value, 0) + $foil * COALESCE(f.field_quantity_foil_value, 0))",
      'total',
      [':factor' => $factor],
    );
    return round((float) $query->execute()->fetchField(), 2);
  }

  /**
   * Published collection rows joined to their card and owned/foil counts.
   */
  private function baseQuery(): SelectInterface {
    $query = $this->database->select('node_field_data', 'cc');
    $query->condition('cc.type', 'collection_card');
    $query->join('node__field_card', 'fc', 'fc.entity_id = cc.nid');
    $query->join('node', 'c', 'c.nid = fc.field_card_target_id');
    $query->join('node_field_data', 'cd', 'cd.nid = c.nid');
    $query->leftJoin('node__field_quantity_owned', 'o', 'o.entity_id = cc.nid');
    $query->leftJoin('node__field_quantity_foil', 'f', 'f.entity_id = cc.nid');
    return $query;
  }

}
