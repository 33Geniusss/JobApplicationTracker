import { t, language, locale } from "/i18n.js";
"use strict";
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const norm = s => s.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();
const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; };
let state = {companies: [], applications: [], token: ""};
let mode = "apps", selected = null, editing = null, deleting = null, pendingBackup = null, toastTimer;
let renderedDate = localDate();

function statusControl(a) {
  const status = a.display_status || a.status || "reviewing";
  return `<div class="status-row"><label>${t("申请状态")} <select class="status-select status-${escapeHTML(status.replaceAll(" ", "-"))}" data-status="${a.id}" aria-label="${escapeHTML(t("{title} 的申请状态", {title:a.title}))}"><option value="reviewing" ${a.status === "reviewing" ? "selected" : ""}>${status === "long reviewing" ? "long reviewing" : "reviewing"}</option><option value="refused" ${a.status === "refused" ? "selected" : ""}>refused</option><option value="accepted" ${a.status === "accepted" ? "selected" : ""}>accepted</option></select></label>${status === "long reviewing" ? `<small>${t("已超过 30 天")}</small>` : ""}</div>`;
}

async function api(path, method="GET", body) {
  let response;
  try {
    response = await fetch(path, {method, headers: {"Content-Type":"application/json", "X-CSRF-Token":state.token, "X-Language":language}, ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  } catch (_) { throw new Error(t("无法连接本地服务，请重新双击启动软件，然后刷新页面。")); }
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || t("操作失败，请重试")); error.data = data; error.status = response.status; throw error; }
  return data;
}

function toast(message, error=false) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  toastTimer = setTimeout(() => $("toast").hidden = true, error ? 9000 : 4000);
}

async function refresh() {
  state = await api("/api/state");
  renderedDate = localDate();
  const categories = [...new Set(state.companies.map(c => c.category))].sort();
  const category = $("category").value;
  $("category").innerHTML = `<option value="">${t("所有领域")}</option>` + categories.map(c => `<option value="${escapeHTML(c)}">${escapeHTML(t(c))}</option>`).join("");
  $("category").value = categories.includes(category) ? category : "";
  $("company-options").innerHTML = state.companies.flatMap(c => [
    `<option value="${escapeHTML(c.name)}">${escapeHTML(language === "en" ? t(c.category) : c.aliases.join(" / ") || c.category)}</option>`,
    ...c.aliases.filter(a => language !== "en" || !/[\u3400-\u9fff]/.test(a)).map(a => `<option value="${escapeHTML(a)}">${escapeHTML(c.name)}</option>`)
  ]).join("");
  $("stat-apps").textContent = state.applications.length;
  $("nav-count").textContent = state.applications.length;
  $("stat-companies").textContent = state.companies.filter(c => c.count).length;
  $("stat-directory").textContent = state.companies.length;
  $("footer-status").textContent = t("本机保存 · 无需登录");
  render();
}

function matchingCompanies() {
  const query = norm($("company-search").value), category = $("category").value;
  return state.companies.filter(c => (!category || c.category === category) &&
    (!query || [c.name, ...c.aliases].some(n => norm(n).includes(query))) &&
    (query || mode === "directory" || c.count > 0))
    .sort((a,b) => Number(b.count > 0) - Number(a.count > 0) || a.name.localeCompare(b.name, "en"));
}

function empty(title, description, action=true, symbol="↗") {
  return `<div class="empty"><div class="empty-icon" aria-hidden="true">${symbol}</div><h3>${escapeHTML(title)}</h3><p>${escapeHTML(description)}</p>${action ? `<button class="secondary empty-add">${t("＋ 记录一份申请")}</button>` : ""}</div>`;
}

function render() {
  const query = norm($("company-search").value);
  $("category").disabled = Boolean(query);
  const companies = matchingCompanies();
  if (selected && !companies.some(c => c.id === selected)) selected = null;
  const company = state.companies.find(c => c.id === selected);
  $("nav-apps").classList.toggle("active", mode === "apps");
  $("nav-directory").classList.toggle("active", mode === "directory");
  $("nav-apps").setAttribute("aria-current", mode === "apps" ? "page" : "false");
  $("nav-directory").setAttribute("aria-current", mode === "directory" ? "page" : "false");
  $("breadcrumb").textContent = mode === "apps" ? t("申请记录") : t("公司名录");
  $("page-title").innerHTML = mode === "apps" ? t('每一步，心中有数<span class="green">。</span>') : t('下一站，从这里开始<span class="green">。</span>');
  $("page-description").textContent = mode === "apps" ? t("把申请留在这里，把精力留给下一次机会。") : t("浏览美国科技公司候选名单，选择公司查看申请情况。");
  $("company-list-title").textContent = query ? t("匹配的公司") : mode === "apps" ? t("已申请公司") : t("公司候选名单");
  $("company-list-count").textContent = t("{count} 家", {count: companies.length});
  $("all-companies").classList.toggle("selected", !selected);
  $("all-companies").innerHTML = query ? t('全部匹配结果<span>→</span>') : mode === "directory" ? t('浏览公司名录<span>→</span>') : t('全部申请<span>→</span>');
  $("search-notice").hidden = !query && mode !== "directory";
  $("search-notice").textContent = query ? t("查询会同时检查公司名录和自定义公司；只有已保存岗位才算已申请。") : t("候选名单含大型公司、初创公司及招聘品牌；不代表当前招聘状态，也不会计入已申请公司。");
  $("company-list").innerHTML = companies.length ? companies.map(c => `<button class="company-row ${c.id === selected ? "selected" : ""}" data-company="${c.id}" aria-pressed="${c.id === selected}" title="${escapeHTML(c.name)}"><span class="company-avatar" aria-hidden="true">${escapeHTML(c.name.slice(0,1).toUpperCase())}</span><span class="company-row-text"><span class="company-name">${escapeHTML(c.name)}</span><span class="company-category">${escapeHTML(t(c.category))}</span></span><span class="company-count ${c.count ? "" : "zero"}">${c.count ? t("{count} 岗位", {count: c.count}) : t("未申请")}</span></button>`).join("") : '<p class="small-empty">' + (query ? t("没有匹配的公司名称<br>可直接输入新公司添加申请") : t("暂无已申请公司<br>保存第一份申请后会显示在这里")) + '</p>';
  const ids = new Set(companies.map(c => c.id));
  let records = state.applications.filter(a => selected ? a.company_id === selected : ids.has(a.company_id));
  const total = records.length;
  const role = norm($("role-search").value);
  records = records.filter(a => norm(a.title).includes(role));
  $("records-title").textContent = company ? company.name : query ? t("“{query}” 的查询结果", {query: $("company-search").value.trim()}) : mode === "directory" ? t("发现更多可能") : t("全部申请");
  $("records-subtitle").textContent = company ? t("{category} · 已申请 {count} 个岗位", {category: t(company.category), count: total}) : query ? t("匹配 {companies} 家公司 · {count} 条申请记录", {companies: companies.length, count: total}) : mode === "directory" ? t("{count} 家候选公司 · 点击左侧公司查看", {count: companies.length}) : t("{count} 条申请记录 · 按申请日期倒序", {count: total});
  if (mode === "directory" && !selected && !query) {
    $("record-list").innerHTML = empty(t("先选一家公司，看看你的足迹"), t("左侧可按领域浏览；也可以搜索英文名或常见中文别名。名单之外的公司同样可以记录。"), false, "▦");
  } else if (records.length) {
    $("record-list").innerHTML = records.map(a => `<article class="record-card"><div class="record-top"><div><span class="company-chip">${escapeHTML(a.company)}</span><h3>${escapeHTML(a.title)}</h3></div><div class="record-actions"><button class="text-button" data-edit="${a.id}" aria-label="${t("编辑")} ${escapeHTML(a.title)}">${t("编辑")}</button><button class="text-button delete" data-delete="${a.id}" aria-label="${t("删除")} ${escapeHTML(a.title)}">${t("删除")}</button></div></div>${statusControl(a)}<div class="record-bottom"><span>${t("已申请")} · ${escapeHTML(a.applied_date.replaceAll("-", "."))}</span>${a.url ? `<a class="job-link" href="${escapeHTML(a.url)}" target="_blank" rel="noopener noreferrer">${t("查看岗位 ↗")}</a>` : `<span>${t("未添加岗位网址")}</span>`}</div></article>`).join("");
  } else if (role && total) {
    $("record-list").innerHTML = empty(t("没有匹配的岗位记录"), t("当前公司范围内未找到该岗位，请尝试更短的岗位名称或清空岗位筛选。"), false, "⌕");
  } else if (company || query) {
    const title = company ? t("尚未申请该公司") : companies.length > 1 ? t("这些公司暂无申请记录") : t("尚未申请该公司");
    $("record-list").innerHTML = empty(title, company ? t("{company} 目前没有已保存的岗位记录。如果已经投递，可以现在补记。", {company: company.name}) : t("没有找到对应的已保存申请。可以选择公司或直接记录一份新申请。"), true, "⌕");
  } else {
    $("record-list").innerHTML = empty($("category").value ? t("这个领域还没有申请记录") : t("从第一份申请开始"), t("公司名称 + 岗位名称，就能记下一次投递。下次只需搜索公司，就知道自己申请过什么。"));
  }
}

function navigate(next) {
  mode = next; selected = null;
  $("company-search").value = ""; $("role-search").value = ""; $("category").value = "";
  render();
}

function openForm(id=null) {
  editing = id;
  $("application-form").reset();
  $("form-error").hidden = true; $("duplicate-box").hidden = true;
  $("form-title").textContent = id ? t("编辑申请记录") : t("记录新申请");
  $("save-button").textContent = id ? t("保存修改") : t("保存申请");
  if (id) {
    const a = state.applications.find(a => a.id === id);
    $("company-input").value = a.company; $("title-input").value = a.title;
    $("url-input").value = a.url; $("date-input").value = a.applied_date;
    $("status-input").value = a.status;
  } else {
    const company = state.companies.find(c => c.id === selected);
    $("company-input").value = company ? company.name : $("company-search").value.trim();
    $("date-input").value = localDate();
  }
  $("application-dialog").showModal();
  ($("company-input").value ? $("title-input") : $("company-input")).focus();
}

$("nav-apps").addEventListener("click", () => navigate("apps"));
$("nav-directory").addEventListener("click", () => navigate("directory"));
$("add-open").addEventListener("click", () => openForm());
$("all-companies").addEventListener("click", () => { selected = null; $("role-search").value = ""; render(); });
$("company-search").addEventListener("input", () => {
  selected = null;
  $("category").value = "";
  $("role-search").value = "";
  const query = norm($("company-search").value);
  const companies = matchingCompanies();
  const exact = companies.find(c => [c.name, ...c.aliases].some(n => norm(n) === query));
  if (exact) selected = exact.id;
  else if (query && companies.length === 1) selected = companies[0].id;
  render();
});
$("category").addEventListener("change", () => { selected = null; render(); });
$("role-search").addEventListener("input", render);
$("company-list").addEventListener("click", event => {
  const button = event.target.closest("[data-company]");
  if (button) { selected = Number(button.dataset.company); $("role-search").value = ""; render(); }
});
$("record-list").addEventListener("click", event => {
  if (event.target.closest(".empty-add")) return openForm();
  const edit = event.target.closest("[data-edit]");
  if (edit) return openForm(edit.dataset.edit);
  const del = event.target.closest("[data-delete]");
  if (del) {
    deleting = del.dataset.delete;
    const a = state.applications.find(a => a.id === deleting);
    $("delete-description").textContent = `${a.company} · ${a.title}`;
    $("delete-dialog").showModal();
  }
});
$("record-list").addEventListener("change", async event => {
  const control = event.target.closest("[data-status]");
  if (!control) return;
  const record = state.applications.find(a => a.id === control.dataset.status);
  const previous = record.status;
  control.disabled = true;
  try {
    await api(`/api/applications/${record.id}`, "PATCH", {status: control.value});
  } catch (error) {
    control.value = previous; control.disabled = false;
    toast(error.message, true);
    return;
  }
  try { await refresh(); toast(t("申请状态已保存")); }
  catch (_) { control.disabled = false; toast(t("状态已保存，但列表刷新失败。请刷新页面。"), true); }
});

document.querySelectorAll(".close-dialog").forEach(button => button.addEventListener("click", () => button.closest("dialog").close()));
["company-input", "title-input"].forEach(id => $(id).addEventListener("input", () => { $("duplicate-box").hidden = true; $("allow-duplicate").checked = false; }));
$("application-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = $("save-button");
  if (button.disabled) return;
  const data = Object.fromEntries(new FormData(event.target));
  data.allow_duplicate = !$("duplicate-box").hidden && $("allow-duplicate").checked;
  button.disabled = true; $("form-error").hidden = true;
  try {
    const result = await api(editing ? `/api/applications/${editing}` : "/api/applications", editing ? "PUT" : "POST", data);
    $("application-dialog").close();
    mode = "apps"; $("company-search").value = ""; $("role-search").value = ""; $("category").value = "";
    try {
      await refresh();
      selected = state.applications.find(a => a.id === result.id)?.company_id || null;
      render();
      toast(editing ? t("修改已保存") : t("申请已记录，继续向前。 "));
    } catch (error) { toast(t("记录已保存，但列表刷新失败。请刷新页面。"), true); }
  } catch (error) {
    if (error.status === 409 && error.data.duplicates?.length) {
      $("duplicate-box").hidden = false;
      $("duplicate-details").textContent = t("已存在 {count} 条同名记录，申请日期：{dates}。", {count: error.data.duplicates.length, dates: error.data.duplicates.map(a => a.applied_date).join(", ")});
      $("allow-duplicate").focus();
    } else { $("form-error").textContent = error.message; $("form-error").hidden = false; }
  } finally { button.disabled = false; }
});

$("delete-confirm").addEventListener("click", async () => {
  const button = $("delete-confirm"); button.disabled = true;
  try { await api(`/api/applications/${deleting}`, "DELETE"); $("delete-dialog").close(); await refresh(); toast(t("申请记录已删除")); }
  catch (error) { $("delete-dialog").close(); toast(error.message, true); }
  finally { button.disabled = false; }
});

$("backup-open").addEventListener("click", () => $("backup-dialog").showModal());
$("backup-quick").addEventListener("click", () => $("backup-dialog").showModal());
$("restore-file").addEventListener("change", async event => {
  pendingBackup = null; $("restore-preview").hidden = true;
  $("restore-result").textContent = ""; $("restore-result").classList.remove("error");
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 20*1024*1024) throw new Error(t("备份文件不能超过 20 MB"));
    const data = JSON.parse(await file.text());
    if (data.format !== "local-job-application-tracker" || ![1, 2].includes(data.version) || !Array.isArray(data.applications)) throw new Error(t("请选择本软件导出的 JSON 备份"));
    pendingBackup = data;
    $("restore-summary").textContent = t("{file} · 包含 {count} 条申请。确认后将合并到本机记录。", {file: file.name, count: data.applications.length});
    $("restore-preview").hidden = false;
  } catch (error) { $("restore-result").textContent = error instanceof SyntaxError ? t("文件不是有效的 JSON 备份。") : error.message; $("restore-result").classList.add("error"); }
  event.target.value = "";
});
$("restore-confirm").addEventListener("click", async () => {
  if (!pendingBackup) return;
  const button = $("restore-confirm"); button.disabled = true;
  try {
    const result = await api("/api/restore", "POST", pendingBackup);
    pendingBackup = null; $("restore-preview").hidden = true;
    $("restore-result").classList.remove("error");
    $("restore-result").textContent = t("恢复完成：新增 {added} 条，跳过 {skipped} 条相同记录。", {added: result.added, skipped: result.skipped});
    await refresh();
  } catch (error) { $("restore-result").textContent = error.message; $("restore-result").classList.add("error"); }
  finally { button.disabled = false; }
});
document.addEventListener("keydown", event => {
  if (event.key === "/" && !document.querySelector("dialog[open]") && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    event.preventDefault(); $("company-search").focus();
  }
});
$("today").textContent = new Date().toLocaleDateString(locale, {year:"numeric", month:"long", day:"numeric", weekday:"short"});
// Re-evaluate waiting status across midnight, including after computer sleep.
function refreshOnNewDay() {
  if (!document.hidden && localDate() !== renderedDate) {
    $("today").textContent = new Date().toLocaleDateString(locale, {year:"numeric", month:"long", day:"numeric", weekday:"short"});
    refresh().catch(() => {});
  }
}
setInterval(refreshOnNewDay, 60000);
document.addEventListener("visibilitychange", refreshOnNewDay);
window.addEventListener("focus", refreshOnNewDay);
refresh().catch(error => {
  $("record-list").innerHTML = empty(t("暂时无法读取记录"), error.message, false, "!");
  $("records-subtitle").textContent = t("请确认本地服务已启动，再刷新页面");
  toast(error.message, true);
});
