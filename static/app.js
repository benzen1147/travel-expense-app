// === 出張旅費精算書 フロントエンド ===

let appConfig = {};
let uploadedFiles = [];

// ── 初期化 ──
document.addEventListener("DOMContentLoaded", async () => {
  await loadConfig();
  checkAuth();
  initDropZone();
  addTransportRow();
  addAccommodationRow();

  // 提出日デフォルト: 今日
  document.getElementById("submissionDate").value = todayStr();

  // リアルタイム計算イベント
  document.getElementById("departureDate").addEventListener("change", recalc);
  document.getElementById("returnDate").addEventListener("change", recalc);
  document.getElementById("applicantRole").addEventListener("change", recalc);
  document.getElementById("isOverseas").addEventListener("change", recalc);

  // OAuth コールバック後の通知
  if (new URLSearchParams(location.search).get("auth") === "success") {
    history.replaceState(null, "", "/");
    checkAuth();
  }
});

function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

// ── 設定読み込み ──
async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    appConfig = await res.json();
    populateTravelers();
  } catch (e) {
    console.error("設定読み込みエラー:", e);
  }
}

function populateTravelers() {
  const sel = document.getElementById("applicantName");
  let defaultName = "";
  (appConfig.travelers || []).forEach(t => {
    const opt = document.createElement("option");
    opt.value = t.name;
    opt.textContent = t.name;
    opt.dataset.role = t.role;
    sel.appendChild(opt);
    if (t.default) defaultName = t.name;
  });
  // デフォルト選択
  if (defaultName) {
    sel.value = defaultName;
    const selected = sel.options[sel.selectedIndex];
    if (selected && selected.dataset.role) {
      document.getElementById("applicantRole").value = selected.dataset.role;
    }
  }
  // 名前選択時に役職を自動設定
  sel.addEventListener("change", () => {
    const selected = sel.options[sel.selectedIndex];
    if (selected.dataset.role) {
      document.getElementById("applicantRole").value = selected.dataset.role;
      recalc();
    }
  });

  // 自由入力用
  const optOther = document.createElement("option");
  optOther.value = "__other__";
  optOther.textContent = "その他（手入力）";
  sel.appendChild(optOther);

  sel.addEventListener("change", () => {
    if (sel.value === "__other__") {
      const name = prompt("出張者名を入力してください");
      if (name) {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        sel.insertBefore(opt, sel.lastElementChild);
        sel.value = name;
      } else {
        sel.value = "";
      }
    }
  });
}

// ── Google認証 ──
async function checkAuth() {
  try {
    const res = await fetch("/api/auth/status");
    const data = await res.json();
    const statusEl = document.getElementById("authStatus");
    const btnEl = document.getElementById("authBtn");

    if (data.authenticated) {
      statusEl.textContent = "Google連携: 認証済み";
      statusEl.className = "status ok";
      btnEl.textContent = "再認証";
      btnEl.style.display = "inline-flex";
    } else if (data.tokenExists && !data.authenticated) {
      statusEl.textContent = "Google連携: トークン期限切れ（再認証してください）";
      statusEl.className = "status no";
      btnEl.textContent = "再認証";
      btnEl.style.display = "inline-flex";
    } else if (data.credentialsConfigured) {
      statusEl.textContent = "Google連携: 未認証（認証するとDrive/Sheets保存が使えます）";
      statusEl.className = "status no";
      btnEl.textContent = "Google認証";
      btnEl.style.display = "inline-flex";
    } else {
      statusEl.textContent = "Google連携: 未設定（PDF生成のみ利用可能）";
      statusEl.className = "status no";
      btnEl.style.display = "none";
    }
  } catch (e) {
    document.getElementById("authStatus").textContent = "Google連携: 確認エラー";
  }
}

async function startAuth() {
  const btn = document.getElementById("authBtn");
  btn.disabled = true;
  btn.textContent = "認証ページへ移動中...";

  try {
    const res = await fetch("/api/auth/start", { method: "POST" });
    const data = await res.json();
    if (data.success && data.authUrl) {
      // Googleの認証ページにリダイレクト
      window.location.href = data.authUrl;
    } else {
      alert("認証エラー: " + (data.error || "不明なエラー"));
      btn.disabled = false;
      btn.textContent = "Google認証";
    }
  } catch (e) {
    alert("認証エラー: " + e.message);
    btn.disabled = false;
    btn.textContent = "Google認証";
  }
}

// ── 動的行管理 ──
function createItemRow(containerId, onChangeCallback) {
  const row = document.createElement("div");
  row.className = "item-row";
  row.innerHTML = `
    <input type="text" placeholder="内容" class="item-desc">
    <input type="number" placeholder="金額" class="item-amount" min="0" step="1">
    <button class="btn-remove" onclick="removeRow(this)" title="削除">&times;</button>
  `;
  document.getElementById(containerId).appendChild(row);

  // リアルタイム計算
  row.querySelectorAll("input").forEach(inp => {
    inp.addEventListener("input", onChangeCallback);
  });
}

function addTransportRow() {
  createItemRow("transportRows", recalc);
}
function addAccommodationRow() {
  const row = document.createElement("div");
  row.className = "item-row item-row-accom";
  const nightsOpts = [1,2,3,4,5,6,7,8,9,10].map(n =>
    `<option value="${n}">${n}泊</option>`
  ).join("");
  row.innerHTML = `
    <input type="text" placeholder="内容" class="item-desc">
    <select class="item-nights">${nightsOpts}</select>
    <input type="number" placeholder="金額" class="item-amount" min="0" step="1">
    <button class="btn-remove" onclick="removeRow(this)" title="削除">&times;</button>
  `;
  document.getElementById("accommodationRows").appendChild(row);
  row.querySelectorAll("input, select").forEach(el => {
    el.addEventListener("input", recalc);
    el.addEventListener("change", recalc);
  });
}

function removeRow(btn) {
  const container = btn.closest(".item-rows");
  btn.closest(".item-row").remove();
  // 最低1行は残す
  if (container.children.length === 0) {
    if (container.id === "transportRows") addTransportRow();
    else addAccommodationRow();
  }
  recalc();
}

// ── 合計計算 ──
function recalc() {
  const transportSum = sumItems("transportRows");
  const accommodationSum = sumItems("accommodationRows");

  document.getElementById("transportTotal").textContent = transportSum.toLocaleString();
  document.getElementById("totalTransport").textContent = `¥ ${transportSum.toLocaleString()}`;

  document.getElementById("accommodationTotal").textContent = accommodationSum.toLocaleString();
  document.getElementById("totalAccommodation").textContent = `¥ ${accommodationSum.toLocaleString()}`;

  // 日当計算
  const dep = document.getElementById("departureDate").value;
  const ret = document.getElementById("returnDate").value;
  const role = document.getElementById("applicantRole").value;
  const overseas = document.getElementById("isOverseas").value === "true";

  let allowance = 0;
  let detail = "-";
  if (dep && ret && role) {
    const d1 = new Date(dep);
    const d2 = new Date(ret);
    const days = Math.floor((d2 - d1) / 86400000) + 1;
    if (days > 0) {
      const region = overseas ? "overseas" : "domestic";
      const rate = appConfig.dailyRates?.[region]?.[role] || 0;
      allowance = days * rate;
      const typeLabel = overseas ? "海外" : "国内";
      const roleLabel = role === "representative" ? "代表社員" : "従業員";
      detail = `${typeLabel}・${roleLabel} ${days}日 × ${rate.toLocaleString()}円`;
    }
  }

  document.getElementById("allowanceDetail").textContent = detail;
  document.getElementById("totalAllowance").textContent = `¥ ${allowance.toLocaleString()}`;

  const grand = transportSum + accommodationSum + allowance;
  document.getElementById("grandTotal").textContent = `¥ ${grand.toLocaleString()}`;

  // 高額宿泊チェック
  checkHighAccommodation();
}

function sumItems(containerId) {
  let sum = 0;
  document.querySelectorAll(`#${containerId} .item-amount`).forEach(inp => {
    sum += parseInt(inp.value) || 0;
  });
  return sum;
}

function checkHighAccommodation() {
  const threshold = appConfig.highAccommodationThreshold || 30000;
  let hasHigh = false;
  document.querySelectorAll("#accommodationRows .item-row").forEach(row => {
    const amount = parseInt(row.querySelector(".item-amount")?.value) || 0;
    const nightsSel = row.querySelector(".item-nights");
    const nights = nightsSel ? (parseInt(nightsSel.value) || 1) : 1;
    if (amount > 0 && (amount / nights) > threshold) hasHigh = true;
  });
  const group = document.getElementById("highReasonGroup");
  if (hasHigh) {
    group.classList.add("show");
  } else {
    group.classList.remove("show");
  }
}

// ── ファイルアップロード ──
function initDropZone() {
  const zone = document.getElementById("dropZone");
  const input = document.getElementById("fileInput");

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("dragover"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("dragover");
    addFiles(e.dataTransfer.files);
  });
  input.addEventListener("change", () => {
    addFiles(input.files);
    input.value = "";
  });
}

function addFiles(fileList) {
  for (const f of fileList) {
    uploadedFiles.push(f);
  }
  renderFileList();
}

function removeFile(idx) {
  uploadedFiles.splice(idx, 1);
  renderFileList();
}

function renderFileList() {
  const list = document.getElementById("fileList");
  list.innerHTML = uploadedFiles.map((f, i) => `
    <div class="file-item">
      <span>${f.name} (${(f.size / 1024).toFixed(1)} KB)</span>
      <button class="btn-remove" onclick="removeFile(${i})" style="width:28px;height:28px;font-size:0.9rem">&times;</button>
    </div>
  `).join("");
}

// ── フォーム送信 ──
async function submitForm() {
  hideErrors();

  const data = collectFormData();

  // クライアントサイドバリデーション
  const errors = validateClient(data);
  if (errors.length) {
    showErrors(errors);
    return;
  }

  showSpinner();

  try {
    const formData = new FormData();
    formData.append("data", JSON.stringify(data));
    uploadedFiles.forEach(f => formData.append("receipts", f));

    const res = await fetch("/api/submit", { method: "POST", body: formData });
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      const text = await res.text();
      throw new Error(`サーバーエラー (${res.status}): ${text.slice(0, 200)}`);
    }
    const result = await res.json();

    hideSpinner();

    if (!result.success) {
      showErrors(result.errors || ["不明なエラーが発生しました。"]);
      return;
    }

    showResult(result);
  } catch (e) {
    hideSpinner();
    showErrors([`通信エラー: ${e.message}`]);
  }
}

function collectFormData() {
  return {
    applicant_name: document.getElementById("applicantName").value,
    applicant_role: document.getElementById("applicantRole").value,
    departure_date: document.getElementById("departureDate").value,
    return_date: document.getElementById("returnDate").value,
    destination: document.getElementById("destination").value,
    purpose: document.getElementById("purpose").value,
    is_overseas: document.getElementById("isOverseas").value === "true",
    submission_date: document.getElementById("submissionDate").value || todayStr(),
    transport_items: collectItems("transportRows"),
    accommodation_items: collectItems("accommodationRows"),
    itinerary_memo: document.getElementById("itineraryMemo").value,
    high_accommodation_reason: document.getElementById("highAccommodationReason").value,
  };
}

function collectItems(containerId) {
  const items = [];
  document.querySelectorAll(`#${containerId} .item-row`).forEach(row => {
    const desc = row.querySelector(".item-desc").value.trim();
    const amount = parseInt(row.querySelector(".item-amount").value) || 0;
    const nightsSel = row.querySelector(".item-nights");
    const nights = nightsSel ? (parseInt(nightsSel.value) || 1) : null;
    if (desc || amount) {
      const item = { desc, amount };
      if (nights !== null) item.nights = nights;
      items.push(item);
    }
  });
  return items;
}

function validateClient(data) {
  const errors = [];
  if (!data.applicant_name || data.applicant_name === "__other__") errors.push("出張者名を入力してください。");
  if (!data.applicant_role) errors.push("役職を選択してください。");
  if (!data.departure_date) errors.push("出発日を入力してください。");
  if (!data.return_date) errors.push("帰着日を入力してください。");
  if (data.departure_date && data.return_date && data.return_date < data.departure_date) {
    errors.push("帰着日は出発日以降にしてください。");
  }
  if (!data.destination.trim()) errors.push("目的地を入力してください。");
  if (!data.purpose.trim()) errors.push("用件を入力してください。");

  // 高額宿泊チェック
  const threshold = appConfig.highAccommodationThreshold || 30000;
  const hasHigh = data.accommodation_items.some(i => i.amount > 0 && (i.amount / (i.nights || 1)) > threshold);
  if (hasHigh && !data.high_accommodation_reason.trim()) {
    errors.push(`1泊${threshold.toLocaleString()}円を超える宿泊があるため、高額宿泊理由を入力してください。`);
  }
  return errors;
}

// ── 結果表示 ──
function showResult(result) {
  const panel = document.getElementById("resultPanel");
  const content = document.getElementById("resultContent");
  const links = document.getElementById("resultLinks");

  content.innerHTML = `<p>合計金額: <strong>¥ ${result.grandTotal.toLocaleString()}</strong></p>`;

  let linksHtml = "";

  // Google Drive フォルダ（目立つボタン）
  if (result.folderUrl) {
    linksHtml += `<a href="${result.folderUrl}" target="_blank" class="btn btn-drive">Google Drive 保存先フォルダを開く</a>`;
  }

  // PDF ダウンロード
  if (result.reportPdf) {
    linksHtml += `<a href="/api/download/${encodeURIComponent(result.reportPdf)}" target="_blank">精算書PDFをダウンロード</a>`;
  }
  if (result.mergedPdf) {
    linksHtml += `<a href="/api/download/${encodeURIComponent(result.mergedPdf)}" target="_blank">結合PDF（領収書付き）をダウンロード</a>`;
  }

  // スプレッドシート
  if (result.sheetUrl) {
    linksHtml += `<a href="${result.sheetUrl}" target="_blank">スプレッドシートを開く</a>`;
  }
  if (result.googleError) {
    linksHtml += `<p style="color:var(--danger); font-size:0.85rem; margin-top:8px">Google保存エラー: ${result.googleError}</p>`;
    if (result.googleTraceback) {
      linksHtml += `<pre style="color:var(--danger); font-size:0.75rem; margin-top:4px; white-space:pre-wrap; background:#fff5f5; padding:8px; border-radius:4px;">${result.googleTraceback}</pre>`;
    }
  }
  links.innerHTML = linksHtml;
  panel.classList.add("show");

  // 結果パネルにスクロール
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  // フォーム部分を少し薄くする
  document.querySelectorAll(".section").forEach(s => s.style.opacity = "0.5");
  document.getElementById("submitBtn").disabled = true;
}

// ── エラー表示 ──
function showErrors(errors) {
  const el = document.getElementById("errorList");
  const ul = document.getElementById("errorItems");
  ul.innerHTML = errors.map(e => `<li>${e}</li>`).join("");
  el.classList.add("show");
  el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function hideErrors() {
  document.getElementById("errorList").classList.remove("show");
}

// ── スピナー ──
function showSpinner() { document.getElementById("spinner").classList.add("active"); }
function hideSpinner() { document.getElementById("spinner").classList.remove("active"); }

// ── リセット ──
function resetForm() {
  document.getElementById("resultPanel").classList.remove("show");
  document.querySelectorAll(".section").forEach(s => s.style.opacity = "1");
  document.getElementById("submitBtn").disabled = false;

  // フォームリセット
  document.getElementById("applicantName").value = "";
  document.getElementById("applicantRole").value = "";
  document.getElementById("departureDate").value = "";
  document.getElementById("returnDate").value = "";
  document.getElementById("destination").value = "";
  document.getElementById("purpose").value = "";
  document.getElementById("isOverseas").value = "false";
  document.getElementById("submissionDate").value = todayStr();
  document.getElementById("itineraryMemo").value = "";
  document.getElementById("highAccommodationReason").value = "";

  // 行リセット
  document.getElementById("transportRows").innerHTML = "";
  document.getElementById("accommodationRows").innerHTML = "";
  addTransportRow();
  addAccommodationRow();

  // ファイルリセット
  uploadedFiles = [];
  renderFileList();

  recalc();
  hideErrors();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
