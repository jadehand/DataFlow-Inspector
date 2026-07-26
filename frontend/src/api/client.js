export function createRuntimeConfig(locationObject = window.location) {
  const params = new URLSearchParams(locationObject.search);
  const suppliedRoot = params.get("api");
  const defaultApi =
    locationObject.port === "15173"
      ? "http://127.0.0.1:18080/api"
      : locationObject.protocol === "file:"
        ? "http://127.0.0.1:18080/api"
        : `${locationObject.origin}/api`;
  const apiRoot = (suppliedRoot || defaultApi).replace(/\/+$/, "");

  return {
    apiOrigin: apiRoot.replace(/\/api\/?$/, ""),
    apiRoot
  };
}

export function createApiClient(config) {
  async function request(path, options) {
    const requestOptions = { ...(options || {}) };
    if (Object.prototype.hasOwnProperty.call(requestOptions, "json")) {
      requestOptions.body = JSON.stringify(requestOptions.json);
      delete requestOptions.json;
      requestOptions.headers = {
        "Content-Type": "application/json",
        ...(requestOptions.headers || {})
      };
    }
    const headers = {
      Accept: "application/json",
      ...(requestOptions.headers || {})
    };
    delete requestOptions.headers;
    const response = await fetch(config.apiRoot + path, {
      headers: {
        ...headers
      },
      ...requestOptions
    });
    const text = await response.text();
    let body = null;

    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }

    if (!response.ok || (body && body.error)) {
      const detail = body && (body.detail || body.error || body.message);
      throw new Error(typeof detail === "string" ? detail : `HTTP ${response.status}`);
    }

    return body;
  }

  return {
    request,
    async download(path) {
      const response = await fetch(config.apiRoot + path, { headers: { Accept: "*/*" } });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.blob();
    },
    href(path) {
      return config.apiRoot + path;
    }
  };
}
