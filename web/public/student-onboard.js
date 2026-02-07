(function () {
  const LS_KEY = "teachproxy_student_api_key";

  const $ = (id) => document.getElementById(id);

  const baseUrl = $("baseUrl");
  const useOriginBtn = $("useOrigin");
  const originText = $("originText");

  const regCode = $("regCode");
  const name = $("name");
  const email = $("email");

  const registerBtn = $("registerBtn");
  const copyCurlBtn = $("copyCurl");
  const openTesterBtn = $("openTester");
  const clearBtn = $("clearBtn");

  const apiKeyOut = $("apiKeyOut");
  const jsonOut = $("jsonOut");
  const statusRow = $("statusRow");

  let lastApiKey = "";

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function setStatus({ ok, httpStatus, requestId, ms }) {
    const parts = [];

    if (typeof httpStatus === "number") {
      parts.push(
        `<span class="pill ${ok ? "ok" : "bad"}"><b>${httpStatus}</b></span>`,
      );
    }
    if (requestId) {
      parts.push(
        `<span class="pill">request_id <b>${escapeHtml(requestId)}</b></span>`,
      );
    }
    if (typeof ms === "number") {
      parts.push(`<span class="pill">time <b>${ms.toFixed(0)}ms</b></span>`);
    }

    statusRow.innerHTML = parts.join("");
  }

  function clearStatus() {
    statusRow.innerHTML = "";
  }

  function getBaseUrl() {
    const raw = (baseUrl.value || "").trim();
    if (!raw) return window.location.origin;
    return raw.replace(/\/+$/, "");
  }

  function setApiKey(v) {
    lastApiKey = v || "";
    apiKeyOut.textContent = lastApiKey ? lastApiKey : "";
    copyCurlBtn.disabled = !lastApiKey;
    openTesterBtn.disabled = !lastApiKey;
  }

  function setJson(objOrText) {
    if (typeof objOrText === "string") {
      jsonOut.textContent = objOrText;
      return;
    }
    jsonOut.textContent = JSON.stringify(objOrText, null, 2);
  }

  function clearOutput() {
    setApiKey("");
    setJson("");
    clearStatus();
  }

  function buildChatCurl() {
    const url = `${getBaseUrl()}/v1/chat/completions`;
    const key = lastApiKey;
    const body = {
      model: "deepseek-chat",
      messages: [{ role: "user", content: "Hello! Please answer in one sentence." }],
      stream: false,
      max_tokens: 128,
      temperature: 0.7,
    };

    return [
      `curl -X POST '${url}' \\`,
      `  -H \"Content-Type: application/json\" \\`,
      `  -H \"Authorization: Bearer ${key.replaceAll('"', '\\"')}\" \\`,
      `  -d '${JSON.stringify(body).replaceAll("'", "'\\''")}'`,
    ].join("\n");
  }

  async function register() {
    clearOutput();

    const code = (regCode.value || "").trim();
    const nm = (name.value || "").trim();
    const em = (email.value || "").trim();

    if (!code) {
      setJson("Missing registration code.");
      setStatus({ ok: false, httpStatus: 0, requestId: "", ms: 0 });
      return;
    }
    if (!nm) {
      setJson("Missing name.");
      return;
    }
    if (!em) {
      setJson("Missing email.");
      return;
    }

    registerBtn.disabled = true;
    const url = `${getBaseUrl()}/v1/student/register`;
    const body = { registration_code: code, name: nm, email: em };
    const t0 = performance.now();

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const ms = performance.now() - t0;
      const requestId =
        res.headers.get("x-request-id") || res.headers.get("X-Request-ID") || "";

      const text = await res.text();
      let json = null;
      try {
        json = JSON.parse(text);
      } catch (_) {
        json = { raw: text };
      }

      setStatus({ ok: res.ok, httpStatus: res.status, requestId, ms });
      setJson(json);

      if (res.ok && json && typeof json.api_key === "string") {
        setApiKey(json.api_key);
      }
    } catch (e) {
      setJson(String(e));
      setStatus({ ok: false, httpStatus: 0, requestId: "", ms: 0 });
    } finally {
      registerBtn.disabled = false;
    }
  }

  originText.textContent = window.location.origin;
  baseUrl.value = window.location.origin;

  useOriginBtn.addEventListener("click", () => {
    baseUrl.value = window.location.origin;
  });

  registerBtn.addEventListener("click", () => {
    register();
  });

  copyCurlBtn.addEventListener("click", async () => {
    if (!lastApiKey) return;
    const txt = buildChatCurl();
    try {
      await navigator.clipboard.writeText(txt);
      setJson("Copied chat curl to clipboard.");
    } catch (_) {
      setJson(txt);
    }
  });

  openTesterBtn.addEventListener("click", () => {
    if (!lastApiKey) return;
    try {
      window.localStorage.setItem(LS_KEY, lastApiKey);
    } catch (_) {
      // ignore
    }
    const url = `${getBaseUrl()}/TeachProxy/student-test.html`;
    window.open(url, "_blank", "noopener,noreferrer");
  });

  clearBtn.addEventListener("click", () => {
    clearOutput();
  });
})();

