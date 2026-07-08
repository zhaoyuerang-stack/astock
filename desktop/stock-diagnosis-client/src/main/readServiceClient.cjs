const DEFAULT_BASE_URL = "http://127.0.0.1:8011";

const NAME_TO_CODE = new Map([
  ["贵州茅台", "600519"],
  ["茅台", "600519"],
  ["宁德时代", "300750"],
  ["宁德", "300750"],
  ["隆基绿能", "601012"],
  ["隆基", "601012"],
]);

function extractStockCode(query) {
  const text = String(query || "").trim();
  const match = text.match(/(?<!\d)(\d{6})(?!\d)/);
  if (match) return match[1];
  for (const [name, code] of NAME_TO_CODE.entries()) {
    if (text.includes(name)) return code;
  }
  return null;
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl || DEFAULT_BASE_URL).replace(/\/+$/, "");
}

function createReadServiceClient(options = {}) {
  const baseUrl = normalizeBaseUrl(options.baseUrl || process.env.ASTOCK_READ_SERVICE_URL);
  const fetchFn = options.fetchFn || globalThis.fetch;
  if (typeof fetchFn !== "function") {
    throw new Error("fetch is required for LocalReadServiceClient");
  }

  async function getJson(path) {
    const response = await fetchFn(`${baseUrl}${path}`);
    if (!response.ok) {
      const body = await response.text().catch(() => "");
      throw new Error(`local read service ${response.status}: ${body || response.statusText}`);
    }
    return response.json();
  }

  return {
    baseUrl,
    extractStockCode,
    async getStockProfile(codeOrQuery) {
      const code = extractStockCode(codeOrQuery);
      if (!code) {
        throw new Error("stock code could not be resolved");
      }
      return getJson(`/data/stocks/${code}`);
    },
  };
}

module.exports = {
  DEFAULT_BASE_URL,
  extractStockCode,
  createReadServiceClient,
};
