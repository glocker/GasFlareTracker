import { fetchEvents } from "#app/api.js";

/** @typedef {import("#app/types.js").FlareEvent} FlareEvent */

const KIND_LABELS = {
  spike: "Spike",
  regime_up: "Regime up",
  regime_down: "Regime down",
};

// Light DOM, same reasoning as facility-card: no third-party markup to wall
// off, so a shadow root would just be extra ceremony.
export class EventFeed extends HTMLElement {
  /** @type {HTMLDialogElement} */
  panel;

  /** @type {HTMLUListElement} */
  list;

  constructor() {
    super();

    // Toggle is outside <dialog>, so clicking it while open would race
    // closedby="any"'s own dismissal - it only opens, closing is the ×
    // button inside instead (CSS hides the toggle while open).
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "event-feed__toggle";
    toggle.setAttribute("aria-label", "Show events");
    toggle.title = "Events";
    toggle.textContent = "☰";
    toggle.addEventListener("click", () => this.panel.show());

    this.panel = document.createElement("dialog");
    this.panel.className = "event-feed__panel";
    // Closes on ESC and on any click outside dialog, same as facility-card
    this.panel.setAttribute("closedby", "any");

    const close = document.createElement("button");
    close.type = "button";
    close.className = "event-feed__close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", () => this.panel.close());

    const title = document.createElement("h2");
    title.textContent = "Flare events";

    this.list = document.createElement("ul");
    this.list.className = "event-feed__list";

    this.panel.append(close, title, this.list);
    this.append(toggle, this.panel);
  }

  connectedCallback() {
    this.loadEvents();
  }

  async loadEvents() {
    /** @type {FlareEvent[]} */
    let events;
    try {
      ({ events } = await fetchEvents());
    } catch (err) {
      console.error("failed to load events", err);
      return;
    }

    this.list.replaceChildren(...events.map((event) => this.renderCard(event)));
  }

  /**
   * Builds one <li> card for the feed list
   * @param {FlareEvent} event - flare_event row joined with facility name
   */
  renderCard(event) {
    const item = document.createElement("li");
    item.className = "event-feed__card";
    item.addEventListener("click", () => {
      item.dispatchEvent(new CustomEvent("event-selected", { detail: event, bubbles: true }));
    });

    const facility = document.createElement("strong");
    facility.textContent = event.facility_name;

    const kind = document.createElement("span");
    kind.className = "event-feed__kind";
    kind.textContent = KIND_LABELS[event.kind];

    const period = document.createElement("span");
    period.className = "event-feed__period";
    // Null end_date means event is still open, no missing data - say so explicitly
    period.textContent = `${event.start_date} – ${event.end_date ?? "Ongoing"}`;

    item.append(facility, kind, period);

    if (event.blind_nights > 0) {
      const blind = document.createElement("span");
      blind.className = "event-feed__blind-badge";
      blind.textContent = `${event.blind_nights} blind night${event.blind_nights === 1 ? "" : "s"}`;
      item.append(blind);
    }

    return item;
  }
}

customElements.define("event-feed", EventFeed);
