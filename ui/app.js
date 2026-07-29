document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatContainer = document.getElementById("chat-container");
    const sendBtn = document.getElementById("send-btn");
    const clearBtn = document.getElementById("clear-btn");
    const csvInput = document.getElementById("csv-input");
    const headerSubtitle = document.getElementById("header-subtitle");
    const welcomeScreen = document.getElementById("welcome-screen");

    // Configure marked to use GitHub Flavored Markdown and line breaks
    if (window.marked) {
        marked.setOptions({
            breaks: true,
            gfm: true
        });
    }

    const userAvatarSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
    const aiAvatarSVG = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path><line x1="8" y1="16" x2="8" y2="16"></line><line x1="16" y1="16" x2="16" y2="16"></line></svg>`;

    function hideWelcomeScreen() {
        welcomeScreen.classList.add("hidden");
    }

    function showWelcomeScreen() {
        chatContainer.querySelectorAll(".message").forEach((el) => el.remove());
        welcomeScreen.classList.remove("hidden");
    }

    function appendMessage(role, content) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}-message`;

        let innerHTML = '';

        if (role === 'ai') {
            innerHTML += `<div class="avatar ai-avatar">${aiAvatarSVG}</div>`;
        }

        let parsedContent = content;
        if (role === 'ai' && window.marked && window.DOMPurify) {
            // Parse markdown and sanitize it to prevent XSS
            const rawHtml = marked.parse(content);
            parsedContent = DOMPurify.sanitize(rawHtml);
        } else if (role === 'user') {
            // Simple text encoding for user messages to avoid XSS
            parsedContent = content.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        innerHTML += `<div class="message-content">${parsedContent}</div>`;

        if (role === 'user') {
            innerHTML += `<div class="avatar user-avatar">${userAvatarSVG}</div>`;
        }

        msgDiv.innerHTML = innerHTML;
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendLoading() {
        const msgDiv = document.createElement("div");
        msgDiv.className = "message ai-message loading-indicator";
        msgDiv.id = "loading-indicator";

        msgDiv.innerHTML = `
            <div class="avatar ai-avatar">${aiAvatarSVG}</div>
            <div class="message-content" style="padding: 12px 16px;">
                <div class="loading-dots">
                    <div class="dot"></div><div class="dot"></div><div class="dot"></div>
                </div>
            </div>
        `;

        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function removeLoading() {
        const loading = document.getElementById("loading-indicator");
        if (loading) {
            loading.remove();
        }
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function setInputState(disabled) {
        userInput.disabled = disabled;
        sendBtn.disabled = disabled;
        if (!disabled) {
            userInput.focus();
        }
    }

    async function sendMessage(text) {
        hideWelcomeScreen();
        appendMessage("user", text);

        setInputState(true);
        appendLoading();

        try {
            const response = await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            removeLoading();
            appendMessage("ai", data.response);

        } catch (error) {
            removeLoading();
            appendMessage("ai", "Sorry, an error occurred while connecting to the server.");
            console.error("Chat error:", error);
        } finally {
            setInputState(false);
        }
    }

    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;
        userInput.value = "";
        sendMessage(text);
    });

    welcomeScreen.addEventListener("click", (e) => {
        const chip = e.target.closest(".suggestion-chip");
        if (!chip) return;

        if (chip.dataset.action === "upload") {
            csvInput.click();
        } else if (chip.dataset.action === "prompt") {
            sendMessage(chip.dataset.prompt);
        }
    });

    csvInput.addEventListener("change", async () => {
        const file = csvInput.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || "Upload failed");
            }

            headerSubtitle.textContent = `Loaded: ${file.name}`;
            hideWelcomeScreen();
            appendMessage("system", `Uploaded "${file.name}". Ask me anything about this data.`);
        } catch (error) {
            hideWelcomeScreen();
            appendMessage("system", `Upload failed: ${error.message}`);
            console.error("Upload error:", error);
        } finally {
            csvInput.value = "";
        }
    });

    clearBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/clear");
            showWelcomeScreen();
        } catch (error) {
            console.error("Failed to clear chat", error);
        }
    });
});
