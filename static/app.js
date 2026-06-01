(() => {
  const maxFields = 40;

  function sizeWord(value) {
    return Number(value) === 5 ? "символов" : "символа";
  }

  function showCopySuccess(button) {
    if (!button) {
      return;
    }

    const original = button.dataset.originalText || button.textContent;
    button.dataset.originalText = original;
    button.textContent = "Скопировано";
    button.classList.add("is-success");

    window.setTimeout(() => {
      button.textContent = original;
      button.classList.remove("is-success");
    }, 1800);
  }

  async function copyText(elementId) {
    const element = document.getElementById(elementId);
    const button = document.getElementById("copyButton");

    if (!element) {
      return;
    }

    const text = element.value || element.textContent || "";

    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const tempTextArea = document.createElement("textarea");
        tempTextArea.value = text;
        tempTextArea.setAttribute("readonly", "");
        tempTextArea.style.position = "fixed";
        tempTextArea.style.top = "-9999px";
        document.body.appendChild(tempTextArea);

        try {
          tempTextArea.select();
          document.execCommand("copy");
        } finally {
          document.body.removeChild(tempTextArea);
        }
      }

      showCopySuccess(button);
    } catch (error) {
      window.alert("Не удалось скопировать текст. Скопируйте вручную: " + text);
    }
  }

  function addUrlField() {
    const container = document.getElementById("additionalFields");

    if (!container) {
      return;
    }

    const currentFields = container.querySelectorAll('input[name="url"]').length;

    if (currentFields >= maxFields) {
      window.alert("Достигнуто максимальное количество полей");
      return;
    }

    const newField = document.createElement("div");
    newField.className = "multi-row";
    newField.innerHTML = `
      <div class="field">
        <label>URL</label>
        <input type="url" class="form-control" name="url" placeholder="https://example.com" required>
      </div>
      <div class="field">
        <label>Описание</label>
        <input type="text" class="form-control" name="description" placeholder="Описание ссылки" required>
      </div>
      <button type="button" class="btn btn-danger" onclick="this.parentElement.remove()">Удалить</button>
    `;

    container.appendChild(newField);
  }

  function checkURLs() {
    const urlInputs = document.querySelectorAll('#urlForm input[name="url"]');
    const urls = [];
    let filledCount = 0;

    for (const input of urlInputs) {
      const url = input.value.trim();

      if (!url) {
        continue;
      }

      filledCount += 1;

      if (urls.includes(url)) {
        window.alert("Нельзя вводить одинаковые URL");
        return false;
      }

      urls.push(url);
    }

    if (filledCount < 2) {
      window.alert("Должно быть заполнено как минимум два поля URL");
      return false;
    }

    return true;
  }

  function initSizeControl() {
    const size = document.getElementById("size");
    const sizeValue = document.getElementById("sizeValue");

    if (!size || !sizeValue) {
      return;
    }

    const update = () => {
      sizeValue.textContent = `${size.value} ${sizeWord(size.value)}`;
    };

    size.addEventListener("input", update);
    update();
  }

  function initCustomCodeToggle() {
    const customCode = document.getElementById("custom_code");
    const sizeBlock = document.getElementById("sizeBlock");

    if (!customCode || !sizeBlock) {
      return;
    }

    const update = () => {
      sizeBlock.hidden = Boolean(customCode.value.trim());
    };

    customCode.addEventListener("input", update);
    update();
  }

  function initUrlInspector() {
    const form = document.getElementById("urlCheckForm");
    const urlInput = document.getElementById("urlInput");

    if (!form || !urlInput) {
      return;
    }

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      form.classList.remove("was-validated");
      urlInput.classList.remove("is-invalid");

      if (!form.checkValidity()) {
        form.classList.add("was-validated");
        return;
      }

      let urlValue = urlInput.value.trim();

      if (!urlValue.startsWith("http://") && !urlValue.startsWith("https://")) {
        urlValue = "https://" + urlValue;
      }

      try {
        const urlObject = new URL(urlValue);
        let path = urlObject.pathname;

        if (path.endsWith("/")) {
          path = path.slice(0, -1);
        }

        if (!path.endsWith("+info")) {
          const segments = path.split("/");
          const lastSegment = segments.pop();
          segments.push(lastSegment + "+info");
          urlObject.pathname = segments.join("/");
        }

        window.location.href = urlObject.href;
      } catch (error) {
        const feedback = urlInput.nextElementSibling;

        if (feedback) {
          feedback.textContent = "Введите корректный URL (пример: https://zezh.ru/abcde)";
        }

        urlInput.classList.add("is-invalid");
      }
    });
  }

  function initQrImage() {
    const qrImage = document.getElementById("qrImage");
    const qrLoader = document.getElementById("qrLoader");

    if (!qrImage || !qrLoader) {
      return;
    }

    const reveal = () => {
      qrLoader.classList.add("d-none");
      qrImage.classList.remove("d-none");
    };

    if (qrImage.complete) {
      reveal();
    } else {
      qrImage.addEventListener("load", reveal, { once: true });
    }
  }

  function initFaviconFallbacks() {
    document.querySelectorAll(".favicon").forEach((image) => {
      image.addEventListener(
        "error",
        () => {
          image.remove();
        },
        { once: true }
      );
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initSizeControl();
    initCustomCodeToggle();
    initUrlInspector();
    initQrImage();
    initFaviconFallbacks();
  });

  window.copyText = copyText;
  window.addUrlField = addUrlField;
  window.checkURLs = checkURLs;
})();
