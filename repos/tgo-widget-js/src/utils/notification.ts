/**
 * Notification and Sound Utilities
 */

// A standard message notification sound
const NOTIFICATION_SOUND_URL = 'https://assets.mixkit.co/active_storage/sfx/2358/2358-preview.mp3';

let audio: HTMLAudioElement | null = null;

/**
 * Play the notification sound
 */
export function playNotificationSound() {
  try {
    if (!audio) {
      audio = new Audio(NOTIFICATION_SOUND_URL);
    }
    audio.currentTime = 0;
    void audio.play().catch(err => {
      console.warn('[Notification] Failed to play sound (likely user interaction required):', err);
    });
  } catch (err) {
    console.warn('[Notification] Error playing sound:', err);
  }
}

/**
 * Show a browser notification
 */
export async function showBrowserNotification(title: string, options?: NotificationOptions) {
  if (!('Notification' in window)) {
    return;
  }

  if (Notification.permission === 'granted') {
    new Notification(title, options);
  } else if (Notification.permission !== 'denied') {
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      new Notification(title, options);
    }
  }
}

/**
 * Request notification permission early
 */
export function requestNotificationPermission() {
  if ('Notification' in window && Notification.permission === 'default') {
    void Notification.requestPermission();
  }
}
