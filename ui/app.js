// Helpers shared by every page. Loaded after config.js.

const SERVICE_NAMES = { PIPELINE_URL: "application pipeline", SKILLS_URL: "skills" };

// Call one of the services and return the JSON body.
// Throws an Error with a readable message on any failure (the body is kept on error.body).
async function api(service, path, options = {}) {
  let response;
  try {
    response = await fetch(window.CONFIG[service] + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    // fetch only throws when there is no answer at all (service down, CORS blocked).
    throw new Error(`Can't reach the ${SERVICE_NAMES[service]} service right now.`);
  }
  const body = await response.json().catch(() => ({}));
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
