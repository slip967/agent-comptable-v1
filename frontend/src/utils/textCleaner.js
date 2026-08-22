const WINDOWS_1252_BYTES = new Map([
  [0x20ac, 0x80], [0x201a, 0x82], [0x0192, 0x83], [0x201e, 0x84],
  [0x2026, 0x85], [0x2020, 0x86], [0x2021, 0x87], [0x02c6, 0x88],
  [0x2030, 0x89], [0x0160, 0x8a], [0x2039, 0x8b], [0x0152, 0x8c],
  [0x017d, 0x8e], [0x2018, 0x91], [0x2019, 0x92], [0x201c, 0x93],
  [0x201d, 0x94], [0x2022, 0x95], [0x2013, 0x96], [0x2014, 0x97],
  [0x02dc, 0x98], [0x2122, 0x99], [0x0161, 0x9a], [0x203a, 0x9b],
  [0x0153, 0x9c], [0x017e, 0x9e], [0x0178, 0x9f],
]);

const MOJIBAKE_PATTERN = /(?:Ã.|Â.|â.|ï¿½|\uFFFD)/u;
const CORRUPTION_PATTERN = /(?:Ã|Â|â|ï¿½|\uFFFD)/gu;

const LEGACY_QUESTION_MARK_REPLACEMENTS = [
  [/\br\?f\?rence(s)?\b/giu, "référence$1"],
  [/\br\?f\?rentiel(s)?\b/giu, "référentiel$1"],
  [/\bd\?tect\?e(s)?\b/giu, "détectée$1"],
  [/\bd\?tect\?(s)?\b/giu, "détecté$1"],
  [/\bm\?tadonn\?e(s)?\b/giu, "métadonnée$1"],
  [/\bm\?tier(s)?\b/giu, "métier$1"],
  [/\bactivit\?(?=\W|$)/giu, "activité"],
  [/\bhypoth\?se(s)?\b/giu, "hypothèse$1"],
  [/\blibell\?(s)?\b/giu, "libellé$1"],
  [/\bt\?l\?communication(s)?\b/giu, "télécommunication$1"],
  [/\bp\?riode(s)?\b/giu, "période$1"],
  [/\bd\?cision(s)?\b/giu, "décision$1"],
  [/\bvalid\?e(s)?\b/giu, "validée$1"],
  [/\bvalid\?(?=\W|$)/giu, "validé"],
  [/\brejet\?e(s)?\b/giu, "rejetée$1"],
  [/\bpropos\?(?=\W|$)/giu, "proposé"],
  [/\brenseign\?(?=\W|$)/giu, "renseigné"],
  [/\bconserv\?e(s)?\b/giu, "conservée$1"],
  [/\bd\?j\?(?=\W|$)/giu, "déjà"],
  [/\bsauvegard\?e(s)?\b/giu, "sauvegardée$1"],
  [/\bsupprim\?e(s)?\b/giu, "supprimée$1"],
  [/\bconfigur\?e(s)?\b/giu, "configurée$1"],
  [/\?lev\?(?=\W|$)/giu, "élevé"],
  [/\btrouv\?(?=\W|$)/giu, "trouvé"],
  [/\? valider\b/giu, "À valider"],
  [/\bn'a \?t\?(?=\W|$)/giu, "n'a été"],
  [/\? \?tudier\b/giu, "à étudier"],
];

function encodeWindows1252(value) {
  const bytes = [];
  for (const character of value) {
    const codePoint = character.codePointAt(0);
    if (codePoint <= 0xff) {
      bytes.push(codePoint);
      continue;
    }
    const mappedByte = WINDOWS_1252_BYTES.get(codePoint);
    if (mappedByte === undefined) return null;
    bytes.push(mappedByte);
  }
  return Uint8Array.from(bytes);
}

function corruptionScore(value) {
  return (String(value).match(CORRUPTION_PATTERN) || []).length
    + (String(value).match(/\uFFFD/gu) || []).length * 4;
}

function decodeMojibakeOnce(value) {
  const bytes = encodeWindows1252(value);
  if (!bytes) return value;
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return value;
  }
}

export function cleanDisplayText(value, fallback = "") {
  if (value === null || value === undefined) return fallback;
  let text = String(value);

  for (let pass = 0; pass < 3 && MOJIBAKE_PATTERN.test(text); pass += 1) {
    const decoded = decodeMojibakeOnce(text);
    if (decoded === text || corruptionScore(decoded) >= corruptionScore(text)) break;
    text = decoded;
  }

  text = LEGACY_QUESTION_MARK_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    text,
  );

  return text
    .replaceAll("ï¿½", "")
    .replaceAll("\uFFFD", "")
    .replaceAll("\u00A0", " ")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/gu, "")
    .replace(/[\u200B-\u200D\u2060\uFEFF]/gu, "")
    .replace(/[ \t]{2,}/gu, " ")
    .trim() || fallback;
}

export function cleanDisplayData(value, seen = new WeakMap()) {
  if (typeof value === "string") return cleanDisplayText(value);
  if (Array.isArray(value)) return value.map((item) => cleanDisplayData(item, seen));
  if (!value || typeof value !== "object" || value instanceof Date) return value;
  if (seen.has(value)) return seen.get(value);

  const cleaned = {};
  seen.set(value, cleaned);
  Object.entries(value).forEach(([key, item]) => {
    cleaned[key] = cleanDisplayData(item, seen);
  });
  return cleaned;
}
