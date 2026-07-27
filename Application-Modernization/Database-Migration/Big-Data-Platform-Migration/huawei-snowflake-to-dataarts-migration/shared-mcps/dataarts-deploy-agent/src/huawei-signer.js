const crypto = require("crypto");

const ALGORITHM = "SDK-HMAC-SHA256";

function hmacSha256(key, message) {
  return crypto.createHmac("sha256", key).update(message).digest();
}

function sha256Hex(data) {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function sortAndFormatHeaders(headers) {
  const lowerEntries = Object.entries(headers).map(([k, v]) => [
    k.toLowerCase().trim(),
    String(v).trim(),
  ]);
  lowerEntries.sort((a, b) => a[0].localeCompare(b[0]));
  const canonical = lowerEntries
    .map(([k, v]) => `${k}:${v}`)
    .join("\n");
  const signed = lowerEntries.map(([k]) => k).join(";");
  return { canonical, signed };
}

function canonicalUri(uri) {
  if (!uri || uri === "/") return "/";
  const segments = uri.split("/").filter(Boolean);
  const encoded = segments.map(encodeURIComponent).join("/");
  return "/" + encoded + "/";
}

function canonicalQueryString(query) {
  if (!query || Object.keys(query).length === 0) return "";
  return Object.entries(query)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .sort()
    .join("&");
}

function formatSdkDate(d) {
  const pad = (n, w) => String(n).padStart(w, "0");
  return (
    pad(d.getUTCFullYear(), 4) +
    pad(d.getUTCMonth() + 1, 2) +
    pad(d.getUTCDate(), 2) +
    "T" +
    pad(d.getUTCHours(), 2) +
    pad(d.getUTCMinutes(), 2) +
    pad(d.getUTCSeconds(), 2) +
    "Z"
  );
}

function signRequest({ method, url, headers, body, ak, sk }) {
  const parsed = new URL(url);
  const datetime = formatSdkDate(new Date());
  const host = parsed.host;

  const reqHeaders = { ...headers, host, "x-sdk-date": datetime };

  const cUri = canonicalUri(parsed.pathname);
  const cQuery = canonicalQueryString(
    Object.fromEntries(parsed.searchParams)
  );
  const { canonical: cHeaders, signed: signedHeaders } =
    sortAndFormatHeaders(reqHeaders);

  const payloadHash = sha256Hex(body || "");

  const canonicalRequest = [
    method.toUpperCase(),
    cUri,
    cQuery,
    cHeaders,
    "",
    signedHeaders,
    payloadHash,
  ].join("\n");

  const stringToSign = [
    ALGORITHM,
    datetime,
    sha256Hex(canonicalRequest),
  ].join("\n");

  const signature = hmacSha256(sk, stringToSign).toString("hex");

  const authorization = `${ALGORITHM} Access=${ak}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

  return {
    authorization,
    "x-sdk-date": datetime,
    host,
  };
}

function buildSignedHeaders({ method, url, headers, body, ak, sk }) {
  const sig = signRequest({ method, url, headers, body, ak, sk });
  return {
    ...headers,
    Host: sig.host,
    "x-sdk-date": sig["x-sdk-date"],
    Authorization: sig.authorization,
  };
}

module.exports = { signRequest, buildSignedHeaders, ALGORITHM };
