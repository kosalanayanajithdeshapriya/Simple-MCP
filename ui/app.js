document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const chatContainer = document.getElementById("chat-container");
    const sendBtn = document.getElementById("send-btn");
    const clearBtn = document.getElementById("clear-btn");

    function appendMessage(role, content) {
        const msgDiv = document.createElement("div");
        msgDiv.className = `message ${role}-message`;
        
        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        contentDiv.textContent = content;
        
        msgDiv.appendChild(contentDiv);
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendLoading() {
        const msgDiv = document.createElement("div");
        msgDiv.className = "message ai-message loading-indicator";
        msgDiv.id = "loading-indicator";
        
        const contentDiv = document.createElement("div");
        contentDiv.className = "message-content";
        
        const dots = document.createElement("div");
        dots.className = "loading-dots";
        dots.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';
        
        contentDiv.appendChild(dots);
        msgDiv.appendChild(contentDiv);
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

    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (!text) return;

        // Display user message
        appendMessage("user", text);
        userInput.value = "";
        
        // Disable input and show loading
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
    });

    clearBtn.addEventListener("click", async () => {
        try {
            await fetch("/api/clear");
            chatContainer.innerHTML = `
                <div class="message system-message">
                    <div class="message-content">Chat history cleared. How can I help you?</div>
                </div>
            `;
        } catch (error) {
            console.error("Failed to clear chat", error);
        }
    });
});
