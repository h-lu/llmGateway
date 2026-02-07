      const LS_KEY = "teachproxy_student_api_key";

      const $ = (id) => document.getElementById(id);

      const baseUrl = $("baseUrl");
      const originText = $("originText");
      const useOriginBtn = $("useOrigin");

      const apiKey = $("apiKey");
      const toggleKey = $("toggleKey");
      const rememberKey = $("rememberKey");
      const forgetKey = $("forgetKey");

      const prompt = $("prompt");
      const model = $("model");
      const maxTokens = $("maxTokens");
      const temperature = $("temperature");
      const stream = $("stream");

      const sendBtn = $("sendBtn");
      const copyCurl = $("copyCurl");
      const clearBtn = $("clearBtn");

      const jsonOut = $("jsonOut");
      const streamOut = $("streamOut");
      const statusRow = $("statusRow");

      function setStatus({ ok, httpStatus, requestId, ms }) {
        const parts = [];

        if (typeof httpStatus === "number") {
          parts.push(
            `<span class="pill ${ok ? "ok" : "bad"}"><b>${httpStatus}</b></span>`
          );
        }
        if (requestId) {
          parts.push(`<span class="pill">request_id <b>${escapeHtml(requestId)}</b></span>`);
        }
        if (typeof ms === "number") {
          parts.push(`<span class="pill">time <b>${ms.toFixed(0)}ms</b></span>`);
        }

        statusRow.innerHTML = parts.join("");
      }

      function clearStatus() {
        statusRow.innerHTML = "";
      }

      function escapeHtml(s) {
        return String(s)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#039;");
      }

      function getBaseUrl() {
        const raw = (baseUrl.value || "").trim();
        if (!raw) return window.location.origin;
        return raw.replace(/\/+$/, "");
      }

      function getKey() {
        return (apiKey.value || "").trim();
      }

      function getBody() {
        const body = {
          model: (model.value || "deepseek-chat").trim(),
          messages: [{ role: "user", content: (prompt.value || "").trim() }],
          max_tokens: Number(maxTokens.value || 2048),
          temperature: Number(temperature.value || 0.7),
          stream: stream.value === "true",
        };
        return body;
      }

      function pretty(obj) {
        return JSON.stringify(obj, null, 2);
      }

      function setJson(text) {
        jsonOut.textContent = text || "";
      }

      function appendStream(text) {
        streamOut.textContent += text;
      }

      function clearOutput() {
        setJson("");
        streamOut.textContent = "";
        clearStatus();
      }

      function loadRememberedKey() {
        const saved = window.localStorage.getItem(LS_KEY);
        if (saved) {
          apiKey.value = saved;
          rememberKey.checked = true;
        }
      }

      function maybeRememberKey() {
        if (rememberKey.checked) {
          window.localStorage.setItem(LS_KEY, getKey());
        } else {
          window.localStorage.removeItem(LS_KEY);
        }
      }

      function buildCurl() {
        const url = `${getBaseUrl()}/v1/chat/completions`;
        const key = getKey();
        const body = getBody();

        return [
          `curl -X POST ${shellQuote(url)} \\`,
          `  -H "Content-Type: application/json" \\`,
          `  -H "Authorization: Bearer ${key.replaceAll('"', '\\"')}" \\`,
          `  -d '${JSON.stringify(body).replaceAll("'", "'\\''")}'`,
        ].join("\n");
      }

      function shellQuote(s) {
        // Best-effort for display only.
        return `'${String(s).replaceAll("'", "'\\''")}'`;
      }

      async function send() {
        clearOutput();
        const key = getKey();
        const body = getBody();

        if (!key) {
          setJson("Missing student API key.");
          setStatus({ ok: false, httpStatus: 0, requestId: "", ms: 0 });
          return;
        }
        if (!body.messages[0].content) {
          setJson("Prompt is empty.");
          return;
        }

        maybeRememberKey();
        sendBtn.disabled = true;

        const url = `${getBaseUrl()}/v1/chat/completions`;
        const t0 = performance.now();

        try {
          const res = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${key}`,
            },
            body: JSON.stringify(body),
          });

          const ms = performance.now() - t0;
          const requestId =
            res.headers.get("x-request-id") ||
            res.headers.get("X-Request-ID") ||
            "";

          setStatus({
            ok: res.ok,
            httpStatus: res.status,
            requestId,
            ms,
          });

          const isStream = body.stream === true;
          if (!isStream) {
            const text = await res.text();
            try {
              setJson(pretty(JSON.parse(text)));
            } catch (_) {
              setJson(text);
            }
            return;
          }

          if (!res.body) {
            setJson("Streaming response has no body.");
            return;
          }

          const reader = res.body.getReader();
          const dec = new TextDecoder();
          let buf = "";

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buf += dec.decode(value, { stream: true });
            const parts = buf.split("\n\n");
            buf = parts.pop() || "";

            for (const part of parts) {
              const line = part.trim();
              if (!line) continue;
              if (line === "data: [DONE]") {
                appendStream("\n[DONE]\n");
                continue;
              }
              if (line.startsWith("data: ")) {
                const jsonStr = line.slice(6);
                try {
                  const data = JSON.parse(jsonStr);
                  const delta =
                    data &&
                    data.choices &&
                    data.choices[0] &&
                    data.choices[0].delta &&
                    data.choices[0].delta.content;
                  if (typeof delta === "string" && delta.length > 0) {
                    appendStream(delta);
                  }
                } catch (e) {
                  appendStream("\n[parse_error] ");
                  appendStream(jsonStr.slice(0, 200));
                  appendStream("\n");
                }
              }
            }
          }
        } catch (e) {
          setJson(String(e));
          setStatus({ ok: false, httpStatus: 0, requestId: "", ms: 0 });
        } finally {
          sendBtn.disabled = false;
        }
      }

      originText.textContent = window.location.origin;
      baseUrl.value = window.location.origin;
      loadRememberedKey();

      useOriginBtn.addEventListener("click", () => {
        baseUrl.value = window.location.origin;
      });

      toggleKey.addEventListener("click", () => {
        const isHidden = apiKey.type === "password";
        apiKey.type = isHidden ? "text" : "password";
        toggleKey.textContent = isHidden ? "Hide" : "Show";
      });

      rememberKey.addEventListener("change", () => {
        maybeRememberKey();
      });

      forgetKey.addEventListener("click", () => {
        window.localStorage.removeItem(LS_KEY);
        rememberKey.checked = false;
        apiKey.value = "";
      });

      copyCurl.addEventListener("click", async () => {
        const txt = buildCurl();
        try {
          await navigator.clipboard.writeText(txt);
          setJson("Copied curl to clipboard.");
        } catch (_) {
          setJson(txt);
        }
      });

      clearBtn.addEventListener("click", () => {
        clearOutput();
      });

      sendBtn.addEventListener("click", () => {
        send();
      });
