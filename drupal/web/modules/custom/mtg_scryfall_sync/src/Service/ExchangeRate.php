<?php

declare(strict_types=1);

namespace Drupal\mtg_scryfall_sync\Service;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\Core\State\StateInterface;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;

/**
 * USD to EUR exchange rate for valuing cards that only have a USD price.
 *
 * Uses the ECB reference rate from Frankfurter, stored in state and
 * refreshed at most once a day. A failed refresh keeps the last rate and is
 * retried after an hour.
 */
final class ExchangeRate {

  private const URL = 'https://api.frankfurter.dev/v1/latest?base=USD&symbols=EUR';

  private const STATE_KEY = 'mtg_scryfall_sync.usd_eur_rate';

  /**
   * Seconds a fetched rate stays fresh.
   */
  private const MAX_AGE = 86400;

  /**
   * Seconds to wait before retrying after a failed fetch.
   */
  private const RETRY_AFTER = 3600;

  /**
   * Used only until the first successful fetch (ECB rate, October 2026).
   */
  private const FALLBACK_RATE = 0.894;

  public function __construct(
    private readonly ClientInterface $httpClient,
    private readonly StateInterface $state,
    private readonly TimeInterface $time,
    private readonly LoggerChannelFactoryInterface $loggerFactory,
  ) {}

  /**
   * Euros per US dollar.
   */
  public function usdToEur(): float {
    $stored = $this->state->get(self::STATE_KEY);
    $stored = is_array($stored) ? $stored : [];
    $rate = isset($stored['rate']) ? (float) $stored['rate'] : 0.0;
    $now = $this->time->getRequestTime();
    $fetched = (int) ($stored['fetched'] ?? 0);
    $attempted = (int) ($stored['attempted'] ?? 0);

    if ($now - $fetched > self::MAX_AGE && $now - $attempted > self::RETRY_AFTER) {
      $fresh = $this->fetch();
      $stored['attempted'] = $now;
      if ($fresh !== NULL) {
        $rate = $fresh;
        $stored['rate'] = $fresh;
        $stored['fetched'] = $now;
      }
      $this->state->set(self::STATE_KEY, $stored);
    }
    return $rate > 0 ? $rate : self::FALLBACK_RATE;
  }

  /**
   * Converts an amount between USD and EUR.
   *
   * @param float $amount
   *   The amount in the source currency.
   * @param bool $toEur
   *   TRUE for USD to EUR, FALSE for EUR to USD.
   */
  public function convert(float $amount, bool $toEur): float {
    $rate = $this->usdToEur();
    return $toEur ? $amount * $rate : $amount / $rate;
  }

  /**
   * Fetches the current rate, or NULL when the request fails.
   */
  private function fetch(): ?float {
    try {
      $response = $this->httpClient->request('GET', self::URL, ['timeout' => 5]);
      $data = json_decode((string) $response->getBody(), TRUE);
      $rate = is_array($data) ? (float) ($data['rates']['EUR'] ?? 0) : 0.0;
      if ($rate > 0) {
        return $rate;
      }
      $this->loggerFactory->get('mtg_scryfall_sync')->warning('Exchange rate response had no EUR rate.');
    }
    catch (GuzzleException $e) {
      $this->loggerFactory->get('mtg_scryfall_sync')->warning('Exchange rate fetch failed: @message', [
        '@message' => $e->getMessage(),
      ]);
    }
    return NULL;
  }

}
