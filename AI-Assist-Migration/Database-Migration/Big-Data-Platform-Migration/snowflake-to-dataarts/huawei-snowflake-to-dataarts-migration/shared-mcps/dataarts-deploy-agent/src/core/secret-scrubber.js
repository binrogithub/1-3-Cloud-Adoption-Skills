const SECRET_PATTERNS = [
  /HUAWEI_AK[=:]\s*\S+/gi,
  /HUAWEI_SK[=:]\s*\S+/gi,
  /\bAK[=:]\s*\S+/gi,
  /\bSK[=:]\s*\S+/gi,
  /secret[_-]?key[=:]\s*\S+/gi,
  /access[_-]?key[=:]\s*\S+/gi,
  /password[=:]\s*\S+/gi,
  /token[=:]\s*\S+/gi,
];

function scrubSecrets(input) {
  const text = String(input ?? "");
  let safe = text;

  for (const pattern of SECRET_PATTERNS) {
    safe = safe.replace(pattern, (match) => {
      const separatorIndex = match.search(/[=:]/);
      if (separatorIndex < 0) return "***REDACTED***";
      return match.slice(0, separatorIndex + 1) + " ***REDACTED***";
    });
  }

  return safe;
}

module.exports = {
  SECRET_PATTERNS,
  scrubSecrets,
};
