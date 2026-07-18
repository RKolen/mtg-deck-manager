<?php

declare(strict_types=1);

namespace Drupal\mtg_card_images\Plugin\QueueWorker;

use Drupal\Core\Plugin\ContainerFactoryPluginInterface;
use Drupal\Core\Queue\Attribute\QueueWorker;
use Drupal\Core\Queue\QueueWorkerBase;
use Drupal\Core\StringTranslation\TranslatableMarkup;
use Drupal\mtg_card_images\CardImageFetcher;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Downloads one Scryfall card image into local media.
 */
#[QueueWorker(
  id: 'mtg_card_image_fetch',
  title: new TranslatableMarkup('MTG card image fetch'),
  cron: ['time' => 30],
)]
final class CardImageFetchWorker extends QueueWorkerBase implements ContainerFactoryPluginInterface {

  public function __construct(
    array $configuration,
    string $plugin_id,
    mixed $plugin_definition,
    private readonly CardImageFetcher $fetcher,
  ) {
    parent::__construct($configuration, $plugin_id, $plugin_definition);
  }

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container, array $configuration, $plugin_id, $plugin_definition): static {
    return new static(
      $configuration,
      $plugin_id,
      $plugin_definition,
      $container->get('mtg_card_images.fetcher'),
    );
  }

  /**
   * {@inheritdoc}
   */
  public function processItem(mixed $data): void {
    $nid = (int) ($data['nid'] ?? 0);
    if ($nid <= 0) {
      return;
    }
    $this->fetcher->fetchNode($nid);
  }

}
