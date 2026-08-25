/**
 * Copy text to the clipboard, returning whether it worked.
 *
 * `navigator.clipboard` only exists in a secure context — HTTPS or localhost.
 * This tool is meant to run on an internal network, so the common deployment is
 * plain HTTP on a LAN address, where the modern API is simply undefined and the
 * copy button would do nothing at all with no explanation.
 *
 * So: try the real API, fall back to the old execCommand path, and report
 * failure honestly so the caller can tell the user to select the text instead
 * of pretending the copy happened.
 */
export async function copyText(text) {
  if (!text) return false;

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Permission denied or insecure context — fall through to the old path.
    }
  }

  try {
    const area = document.createElement("textarea");
    area.value = text;
    // Keep it out of view and out of the tab order, but still selectable.
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.top = "-1000px";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  } catch {
    return false;
  }
}
