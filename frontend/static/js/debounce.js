/**
 * Basic debounce function
 * @param {(...args: any[]) => void} callback - function to be debounced
 * @param {number} delay - wait in ms
 */
export function debounce(callback, delay) {
  /** @type {number | undefined} */
  let timeoutId;
  return (/** @type {any[]} */ ...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => {
      callback(...args);
    }, delay);
  };
}
