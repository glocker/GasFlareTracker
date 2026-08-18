// Static facility fields only for now (facility_status has no linked event for now)
/** @typedef {import("#app/types.js").FacilityProperties} FacilityProperties */

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
    this.render(/** @type {CustomEvent<FacilityProperties>} */ (e).detail);
  };

  /** @param {FacilityProperties} props */
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
    /**
     * @param {string} name - Property name (Kind, Operator, Status and etc)
     * @param {string | null | undefined} value - Property value
    */
    const addRow = (name, value) => {
      const rowName = document.createElement("dt");
      rowName.textContent = name;

      const rowValue = document.createElement("dd");
      rowValue.textContent = value ?? "—";

      list.append(rowName, rowValue);
    };
    addRow("Kind", props.kind);
    addRow("Operator", props.operator);
    addRow("Status", props.status);

    this.dialog.append(close, title, list);
    this.dialog.show();
  }
}

customElements.define("facility-card", FacilityCard);
