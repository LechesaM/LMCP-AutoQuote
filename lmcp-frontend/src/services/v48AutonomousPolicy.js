const API = "http://localhost:8000";

async function post(path, body) {
  return fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function enableFullSubmission() {
  return post("/v48-autonomous/policy", {
    enabled: true,
    mode: "full_autonomous",
    allow_email_send: true,
    allow_portal_upload: true,
    allow_portal_final_submit: true,
    require_confirmation_phrase: false,
  });
}

export function enableSafeMode() {
  return post("/v48-autonomous/policy", {
    enabled: true,
    mode: "controlled",
    allow_email_send: false,
    allow_portal_upload: true,
    allow_portal_final_submit: false,
    require_confirmation_phrase: true,
  });
}

export function switchSystemOff() {
  return post("/v48-autonomous/policy", {
    enabled: false,
  });
}

export function runAutonomousOnce() {
  return post("/autonomous/run-once", {});
}
