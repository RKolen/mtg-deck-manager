<?php

declare(strict_types=1);

namespace Drupal\mtg_card_images;

use Drupal\Component\Datetime\TimeInterface;
use Drupal\Core\Cache\CacheBackendInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\File\FileExists;
use Drupal\Core\File\FileSystemInterface;
use Drupal\Core\File\FileUrlGeneratorInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\Core\Queue\QueueFactory;
use Drupal\file\FileRepositoryInterface;
use Drupal\media\MediaInterface;
use Drupal\node\NodeInterface;
use GuzzleHttp\ClientInterface;
use Psr\Log\LoggerInterface;

/**
 * Downloads Scryfall card art into media and attaches it to mtg_card nodes.
 */
final class CardImageFetcher {

  public const QUEUE_ID = 'mtg_card_image_fetch';

  public const MEDIA_BUNDLE = 'mtg_card_art';

  public const FIELD_LOCAL = 'field_image_local';

  /**
   * Minimum delay between outbound Scryfall image requests (microseconds).
   */
  private const THROTTLE_US = 150000;

  private const USER_AGENT = 'MTGDeckManager/1.0 (local; card art cache; +https://github.com/local/mtg)';

  private const DIRECTORY = 'public://mtg_cards';

  private readonly LoggerInterface $logger;

  private static ?int $lastFetchAt = NULL;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly ClientInterface $httpClient,
    private readonly FileRepositoryInterface $fileRepository,
    private readonly FileSystemInterface $fileSystem,
    private readonly FileUrlGeneratorInterface $fileUrlGenerator,
    private readonly QueueFactory $queueFactory,
    private readonly CacheBackendInterface $cache,
    LoggerChannelFactoryInterface $loggerFactory,
    private readonly TimeInterface $time,
  ) {
    $this->logger = $loggerFactory->get('mtg_card_images');
  }

  /**
   * Absolute URL for a card's local media image, or NULL if not cached yet.
   */
  public function localUrl(?NodeInterface $node): ?string {
    if ($node === NULL || !$node->hasField(self::FIELD_LOCAL) || $node->get(self::FIELD_LOCAL)->isEmpty()) {
      return NULL;
    }
    $media = $node->get(self::FIELD_LOCAL)->entity;
    if (!$media instanceof MediaInterface) {
      return NULL;
    }
    if (!$media->hasField('field_media_image') || $media->get('field_media_image')->isEmpty()) {
      return NULL;
    }
    $file = $media->get('field_media_image')->entity;
    if ($file === NULL) {
      return NULL;
    }
    return $this->fileUrlGenerator->generateAbsoluteString($file->getFileUri());
  }

  /**
   * Queues a card for image download if it still needs one.
   */
  public function enqueueNode(NodeInterface $node): void {
    if (!$this->needsFetch($node)) {
      return;
    }
    $nid = (int) $node->id();
    $cid = 'mtg_card_images:queued:' . $nid;
    if ($this->cache->get($cid)) {
      return;
    }
    $this->queueFactory->get(self::QUEUE_ID)->createItem(['nid' => $nid]);
    $this->cache->set($cid, TRUE, $this->time->getRequestTime() + 3600);
  }

  /**
   * Queues many node IDs; returns how many were newly queued.
   *
   * @param list<int|string> $nids
   */
  public function enqueueNids(array $nids): int {
    $queued = 0;
    $storage = $this->entityTypeManager->getStorage('node');
    foreach ($nids as $nid) {
      $node = $storage->load((int) $nid);
      if (!$node instanceof NodeInterface) {
        continue;
      }
      if (!$this->needsFetch($node)) {
        continue;
      }
      $before = $this->cache->get('mtg_card_images:queued:' . (int) $node->id());
      $this->enqueueNode($node);
      if (!$before) {
        $queued++;
      }
    }
    return $queued;
  }

  /**
   * Downloads and attaches art for one card. Idempotent.
   */
  public function fetchNode(int $nid): bool {
    $node = $this->entityTypeManager->getStorage('node')->load($nid);
    if (!$node instanceof NodeInterface || $node->bundle() !== 'mtg_card') {
      return FALSE;
    }
    if (!$this->needsFetch($node)) {
      return TRUE;
    }

    $uri = trim((string) ($node->get('field_image_uri')->value ?? ''));
    if ($uri === '' || !str_starts_with($uri, 'https://cards.scryfall.io/')) {
      $this->logger->warning('Card @nid has no usable Scryfall image URI.', ['@nid' => $nid]);
      return FALSE;
    }

    $this->throttle();

    $path = (string) (parse_url($uri, PHP_URL_PATH) ?? '');
    $basename = basename($path);
    if ($basename === '' || $basename === '/' || !preg_match('/^[a-f0-9-]{36}\.jpg$/i', $basename)) {
      $basename = preg_replace('/[^a-zA-Z0-9._-]/', '_', $basename ?? '') ?: ('card-' . $nid . '.jpg');
    }
    $destination = self::DIRECTORY . '/' . strtolower($basename);

    $this->fileSystem->prepareDirectory(self::DIRECTORY, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);

    try {
      $response = $this->httpClient->request('GET', $uri, [
        'headers' => [
          'User-Agent' => self::USER_AGENT,
          'Accept' => 'image/jpeg,image/*;q=0.8,*/*;q=0.5',
        ],
        'http_errors' => TRUE,
        'timeout' => 30,
      ]);
      $data = (string) $response->getBody();
    }
    catch (\Throwable $e) {
      $this->logger->error('Failed to download image for card @nid: @m', [
        '@nid' => $nid,
        '@m' => $e->getMessage(),
      ]);
      return FALSE;
    }

    if ($data === '') {
      $this->logger->error('Empty image body for card @nid.', ['@nid' => $nid]);
      return FALSE;
    }

    $file = $this->fileRepository->writeData($data, $destination, FileExists::Replace);
    $file->setPermanent();
    $file->save();

    $media_storage = $this->entityTypeManager->getStorage('media');
    /** @var \Drupal\media\MediaInterface $media */
    $media = $media_storage->create([
      'bundle' => self::MEDIA_BUNDLE,
      'name' => $node->label() . ' (' . $nid . ')',
      'uid' => 1,
      'status' => 1,
      'field_media_image' => [
        'target_id' => $file->id(),
        'alt' => $node->label(),
      ],
    ]);
    $media->save();

    $node->set(self::FIELD_LOCAL, ['target_id' => $media->id()]);
    $node->save();

    $this->cache->delete('mtg_card_images:queued:' . $nid);
    $this->logger->notice('Cached Scryfall art for card @nid (@title).', [
      '@nid' => $nid,
      '@title' => $node->label(),
    ]);
    return TRUE;
  }

  /**
   * Whether the node still needs a local image download.
   */
  public function needsFetch(NodeInterface $node): bool {
    if ($node->bundle() !== 'mtg_card') {
      return FALSE;
    }
    if (!$node->hasField(self::FIELD_LOCAL) || !$node->hasField('field_image_uri')) {
      return FALSE;
    }
    if (!$node->get(self::FIELD_LOCAL)->isEmpty()) {
      return FALSE;
    }
    $uri = trim((string) ($node->get('field_image_uri')->value ?? ''));
    return $uri !== '' && str_starts_with($uri, 'https://cards.scryfall.io/');
  }

  /**
   * Enforces Scryfall-friendly spacing between HTTP fetches in this process.
   */
  private function throttle(): void {
    $now = (int) round(microtime(TRUE) * 1000000);
    if (self::$lastFetchAt !== NULL) {
      $elapsed = $now - self::$lastFetchAt;
      if ($elapsed < self::THROTTLE_US) {
        usleep(self::THROTTLE_US - $elapsed);
      }
    }
    self::$lastFetchAt = (int) round(microtime(TRUE) * 1000000);
  }

}
