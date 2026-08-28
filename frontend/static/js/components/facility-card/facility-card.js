/** @typedef {import("#app/types.js").FacilitySelection} FacilitySelection */

const EVENT_KIND_LABELS = {
  spike: "Spike",
  regime_up: "Regime up",
  regime_down: "Regime down",
};

/**
 * Appends a name/value row to a <dl>
 * @param {HTMLDListElement} dl - target list to append the row to
 * @param {string} name - property name (Kind, Operator, Status and etc)
 * @param {string | null | undefined} value - property value
 */
function addRow(dl, name, value) {
  const rowName = document.createElement("dt");
  rowName.textContent = name;

  const rowValue = document.createElement("dd");
  rowValue.textContent = value ?? "—";

  dl.append(rowName, rowValue);
}

export class FacilityCard extends HTMLElement {
  /** @type {HTMLDialogElement} */
  dialog;

  constructor() {
    super();
    this.dialog = document.createElement("dialog");
    // Сloses on ESC and on any click outside dialog
    this.dialog.setAttribute("closedby", "any");
    this.append(this.dialog);
  }

  connectedCallback() {
    // Listener on external target needs connect/disconnect pairing
    document.addEventListener("facility-selected", this._onFacilitySelected);
  }

  disconnectedCallback() {
    document.removeEventListener("facility-selected", this._onFacilitySelected);
  }

  /**
   * Renders facility card when user clicked on point
   * @param {Event} e - facility-selected event
   */
  _onFacilitySelected = (e) => {
    this.render(/** @type {CustomEvent<FacilitySelection>} */ (e).detail);
  };

  /** @param {FacilitySelection} props */
  render(props) {
    this.dialog.replaceChildren();

    const close = document.createElement("button");
    close.className = "facility-card__close";
    close.setAttribute("aria-label", "Close");
    close.textContent = "×";
    close.addEventListener("click", () => {
      this.dialog.close();
    });

    const title = document.createElement("h2");
    title.textContent = props.name;

    const list = document.createElement("dl");
    addRow(list, "Kind", props.kind);
    addRow(list, "Operator", props.operator);
    addRow(list, "Status", props.status);

    this.dialog.append(close, title, list);

    // Only set when opened from an event feed card, not from map click
    if (props.event) {
      const eventTitle = document.createElement("h3");
      eventTitle.textContent = "Flare event";

      const eventList = document.createElement("dl");
      addRow(eventList, "Kind", EVENT_KIND_LABELS[props.event.kind]);
      addRow(eventList, "Period", `${props.event.start_date} – ${props.event.end_date ?? "—"}`);
      addRow(eventList, "Score", props.event.score.toFixed(2));
      if (props.event.blind_nights > 0) {
        addRow(eventList, "Blind nights", String(props.event.blind_nights));
      }

      this.dialog.append(eventTitle, eventList);
    }

    this.dialog.show();
  }
}

customElements.define("facility-card", FacilityCard);
