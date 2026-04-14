(() => {
  const configElement = document.getElementById("meeting-notification-config");
  if (!configElement) {
    return;
  }

  const endpoint = configElement.dataset.endpoint || "/notifications/meeting-status";
  const pollSeconds = Number(configElement.dataset.pollSeconds || "60");
  const repeatMinutes = Number(configElement.dataset.repeatMinutes || "10");
  const localStorageKey = "meeting_notifications:last_shown_at";

  function notificationsSupported() {
    return "Notification" in window;
  }

  async function ensureNotificationPermission() {
    if (!notificationsSupported()) {
      return "unsupported";
    }

    if (Notification.permission === "granted") {
      return "granted";
    }

    if (Notification.permission === "denied") {
      return "denied";
    }

    return Notification.requestPermission();
  }

  function recentlyShownOnThisBrowser() {
    const lastShownRaw = window.localStorage.getItem(localStorageKey);
    if (!lastShownRaw) {
      return false;
    }

    const lastShown = Number(lastShownRaw);
    if (!Number.isFinite(lastShown)) {
      return false;
    }

    return Date.now() - lastShown < repeatMinutes * 60 * 1000;
  }

  function markShownNow() {
    window.localStorage.setItem(localStorageKey, String(Date.now()));
  }

  function buildAbsoluteUrl(pathOrUrl) {
    return new URL(pathOrUrl, window.location.origin).toString();
  }

  function navigateToNotificationTarget(payload) {
    const targetUrl = buildAbsoluteUrl(payload.redirect_url || "/meeting-inbox");

    try {
      window.focus();
    } catch (error) {
      console.debug("Meeting notifications: window focus failed.", error);
    }

    try {
      window.location.href = targetUrl;
      return;
    } catch (error) {
      console.debug("Meeting notifications: same-tab redirect failed.", error);
    }

    window.open(targetUrl, "_self");
  }

  function showMeetingNotification(payload) {
    const notification = new Notification(payload.title, {
      body: payload.body,
      tag: "meeting-email-attention",
      renotify: true,
      requireInteraction: true,
    });

    notification.onclick = () => {
      navigateToNotificationTarget(payload);
      notification.close();
    };

    markShownNow();
    console.debug("Meeting notifications: popup shown.", payload);
  }

  async function pollMeetingStatus() {
    try {
      const response = await fetch(endpoint, {
        method: "GET",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        console.warn("Meeting notifications: endpoint returned non-OK status.", response.status);
        return;
      }

      const payload = await response.json();
      console.debug("Meeting notifications: payload received.", payload);

      const debugElement = document.getElementById("meeting-notification-debug");
      if (debugElement) {
        debugElement.textContent =
          `pending=${payload.pending_count ?? 0}, should_notify=${String(payload.should_notify)}, reason=${payload.reason || ""}, title=${payload.title || ""}`;
      }

      if (!payload.should_notify) {
        return;
      }

      if (recentlyShownOnThisBrowser()) {
        console.debug("Meeting notifications: suppressed due to repeat interval.");
        return;
      }

      const permission = await ensureNotificationPermission();
      if (permission !== "granted") {
        console.warn("Meeting notifications: permission not granted.", permission);
        return;
      }

      showMeetingNotification(payload);
    } catch (error) {
      console.error("Meeting notifications: poll failed.", error);
    }
  }

  async function initializeNotifications() {
    const enableButton = document.getElementById("enable-meeting-notifications");
    if (enableButton) {
      enableButton.addEventListener("click", async () => {
        const permission = await ensureNotificationPermission();
        console.debug("Meeting notifications: permission result after button click.", permission);
        await pollMeetingStatus();
      });
    }

    await pollMeetingStatus();
    window.setInterval(pollMeetingStatus, Math.max(pollSeconds, 15) * 1000);
  }

  initializeNotifications();
})();