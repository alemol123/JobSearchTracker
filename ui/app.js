// Helpers shared by every page. Loaded after config.js.

const SERVICE_NAMES = { PIPELINE_URL: "application pipeline", SKILLS_URL: "skills" };

// Cold starts on Azure: a service that scaled to zero needs up to about a minute to start
// (container start, database resume, migrations). Meanwhile the platform answers with a
// 502/503/504 that has no JSON body and no CORS headers, so the browser may only see a
// network error. Both cases count as "still waking up".
const REQUEST_TIMEOUT_MS = 45000;       // never let a request hang: give up after 45 s
const WAKE_RETRIES = 2;                 // reads (GET) are retried this many times
const WAKE_RETRY_DELAY_MS = 5000;

// Same words for "starting up" and "really down": from the browser the two look identical.
function wakingUpMessage(service) {
  return `The ${SERVICE_NAMES[service]} service isn't answering yet (it sleeps when nobody ` +
         "uses it and needs up to a minute to start). Try again in a minute.";
}

// One request with a time limit. Returns the response, or null if there was no answer.
async function fetchOnce(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { headers: { "Content-Type": "application/json" }, ...options,
                              signal: controller.signal });
  } catch {
    return null;                        // no answer: service down, starting up, CORS blocked, timeout
  } finally {
    clearTimeout(timer);
  }
}

// Call one of the services and return the JSON body.
// Throws an Error with a readable message on any failure (the body is kept on error.body).
async function api(service, path, options = {}) {
  const url = window.CONFIG[service] + path;
  // Only reads are retried: repeating a POST could, for example, create an application twice.
  const retries = (options.method || "GET") === "GET" ? WAKE_RETRIES : 0;
  let response, body;
  for (let attempt = 0; ; attempt++) {
    response = await fetchOnce(url, options);
    body = response ? await response.json().catch(() => null) : null;
    // Our services always answer errors with JSON; an answer without JSON (or none at all)
    // comes from the platform while the service is not up yet.
    const wakingUp = response === null || ([502, 503, 504].includes(response.status) && body === null);
    if (!wakingUp) break;
    if (attempt >= retries) {
      const error = new Error(wakingUpMessage(service));
      error.status = response ? response.status : 503;
      throw error;
    }
    showMessage(`Waking up the ${SERVICE_NAMES[service]} service, this can take up to a minute…`);
    await new Promise((resolve) => setTimeout(resolve, WAKE_RETRY_DELAY_MS));
    clearMessage();
  }
  body = body || {};
  if (!response.ok) {
    const message = body.error || (body.errors || []).join(" ") || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }
  return body;
}

// POST/PUT/DELETE with a JSON body.
function send(service, path, method, data) {
  return api(service, path, { method, body: data === undefined ? undefined : JSON.stringify(data) });
}

// Build an element. Strings become text nodes (never HTML), so user data can't inject markup.
// el("a", { href: "x.html", class: "btn" }, "Click")  ->  <a href="x.html" class="btn">Click</a>
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
  }
  for (const child of children.flat(Infinity)) {      // lists of children can be nested
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

// Replaces Flask's flash(): show one message (or a list of messages) at the top of the page.
function showMessage(text, kind = "info") {
  const box = document.getElementById("messages");
  const content = Array.isArray(text) ? el("ul", {}, text.map((t) => el("li", {}, t))) : text;
  box.replaceChildren(el("div", { class: `alert ${kind}` }, content));
}

function clearMessage() {
  document.getElementById("messages").replaceChildren();
}

// ?id=3 in the page URL -> "3"
function queryId() {
  return new URLSearchParams(location.search).get("id");
}

// "phone_screen" -> "phone screen"
function label(value) {
  return String(value).replaceAll("_", " ");
}

function stageBadge(stage) {
  return el("span", { class: `badge stage-${stage}` }, label(stage));
}

// A form's fields as a plain object: { company: "Acme", ... }
function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}
