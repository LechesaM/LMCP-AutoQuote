export async function httpxAdapter(path, config = {}) {
  const response = await fetch(path, {
    method: config.method || "GET",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(config.headers || {}),
    },
    body: config.body ? JSON.stringify(config.body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`HTTP error ${response.status}`);
  }

  return response.json();
}
