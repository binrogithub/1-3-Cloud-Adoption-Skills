import crypto from "crypto";

function sha256Hex(data) {
  return crypto.createHash("sha256").update(data, "utf8").digest("hex");
}

function hmacSha256Hex(key, data) {
  return crypto.createHmac("sha256", key).update(data, "utf8").digest("hex");
}

function formatSdkDate(date = new Date()) {
  const pad = (n) => String(n).padStart(2, "0");
  return (
    date.getUTCFullYear() +
    pad(date.getUTCMonth() + 1) +
    pad(date.getUTCDate()) +
    "T" +
    pad(date.getUTCHours()) +
    pad(date.getUTCMinutes()) +
    pad(date.getUTCSeconds()) +
    "Z"
  );
}

function canonicalQueryString(url) {
  const params = [...url.searchParams.entries()];
  params.sort(([a], [b]) => a.localeCompare(b));

  return params
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
}

export function signHuaweiRequest({ method, url, body, ak, sk }) {
  const parsedUrl = new URL(url);
  const sdkDate = formatSdkDate();

  const payload = body ? JSON.stringify(body) : "";
  const payloadHash = sha256Hex(payload);

  const canonicalHeaders =
    `content-type:application/json;charset=UTF-8\n` +
    `host:${parsedUrl.host}\n` +
    `x-sdk-date:${sdkDate}\n`;

  const signedHeaders = "content-type;host;x-sdk-date";

  const canonicalRequest = [
    method.toUpperCase(),
    parsedUrl.pathname || "/",
    canonicalQueryString(parsedUrl),
    canonicalHeaders,
    signedHeaders,
    payloadHash
  ].join("\n");

  const algorithm = "SDK-HMAC-SHA256";
  const stringToSign = [
    algorithm,
    sdkDate,
    sha256Hex(canonicalRequest)
  ].join("\n");

  const signature = hmacSha256Hex(sk, stringToSign);

  const authorization =
    `${algorithm} Access=${ak}, ` +
    `SignedHeaders=${signedHeaders}, ` +
    `Signature=${signature}`;

  return {
    headers: {
      "Content-Type": "application/json;charset=UTF-8",
      "X-Sdk-Date": sdkDate,
      "Authorization": authorization
    },
    body: payload
  };
}
