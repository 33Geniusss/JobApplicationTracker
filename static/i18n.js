// Chinese source keys pair with the English entries in locales/en.json.
let savedLanguage;
try { savedLanguage = localStorage.getItem("application-notebook-language"); } catch (_) { /* Storage may be disabled. */ }
const requestedLanguage = new URLSearchParams(location.search).get("lang");
export const language = ["zh", "en"].includes(requestedLanguage) ? requestedLanguage : savedLanguage === "en" ? "en" : "zh";
export const locale = language === "en" ? "en-US" : "zh-CN";
const response = await fetch(`/locales/${language}.json`);
if (!response.ok) throw new Error("Unable to load language resources / 无法读取语言文件");
const messages = await response.json();
export function t(key, params = {}) {
  let template = messages[key] ?? key;
  if (language === "en" && params.count === 1) {
    template = template.replace("{count} companies", "{count} company").replace("{count} roles", "{count} role")
      .replace("{count} applications", "{count} application").replace("There are {count} records", "There is {count} record");
  }
  if (language === "en" && params.companies === 1) template = template.replace("{companies} matching companies", "{companies} matching company");
  return template.replace(/\{(\w+)\}/g, (match, name) => Object.hasOwn(params, name) ? String(params[name]) : match);
}

// Translate only the initial static document. User-supplied text is rendered later
// and is never passed through a DOM translation observer.
const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node = walker.currentNode;
  if (["SCRIPT", "STYLE"].includes(node.parentElement?.tagName)) continue;
  const key = node.nodeValue.trim();
  if (Object.hasOwn(messages, key)) node.nodeValue = node.nodeValue.replace(key, messages[key]);
}
document.querySelectorAll("[placeholder], [aria-label], [title]").forEach(element => {
  for (const attribute of ["placeholder", "aria-label", "title"]) {
    if (element.hasAttribute(attribute)) element.setAttribute(attribute, t(element.getAttribute(attribute)));
  }
});
document.documentElement.lang = locale;
const button = document.getElementById("language-toggle");
button.textContent = language === "en" ? "中文" : "English";
button.setAttribute("aria-label", language === "en" ? "切换到中文" : "Switch to English");
button.addEventListener("click", () => {
  const next = language === "en" ? "zh" : "en";
  try { localStorage.setItem("application-notebook-language", next); } catch (_) { /* URL remains a fallback. */ }
  const url = new URL(location.href);
  url.searchParams.set("lang", next);
  location.assign(url);
});
try { localStorage.setItem("application-notebook-language", language); } catch (_) { /* Preference is optional. */ }
