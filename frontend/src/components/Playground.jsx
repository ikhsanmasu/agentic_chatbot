import { useState, useRef, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";

export default function Playground({ chat, onUpdateChat, onNewChat }) {
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [chat?.messages]);

  // Auto-resize textarea
  const handleInput = (e) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isStreaming || !chat) return;

    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setIsStreaming(true);

    // Add user message + empty assistant message
    const userMsg = { role: "user", content: text };
    const assistantMsg = {
      role: "assistant",
      content: "",
      thinking: "",
      isStreaming: true,
    };

    onUpdateChat((c) => ({
      ...c,
      title: c.messages.length === 0 ? text.slice(0, 40) : c.title,
      messages: [...c.messages, userMsg, assistantMsg],
    }));

    try {
      const response = await fetch(`${API_BASE}/v1/chatbot/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let partial = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        partial += decoder.decode(value, { stream: true });
        const lines = partial.split("\n");
        partial = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          const data = JSON.parse(line.slice(6));

          if (data.type === "thinking") {
            onUpdateChat((c) => {
              const msgs = [...c.messages];
              const last = { ...msgs[msgs.length - 1] };
              last.thinking += data.content;
              msgs[msgs.length - 1] = last;
              return { ...c, messages: msgs };
            });
          }

          if (data.type === "content") {
            onUpdateChat((c) => {
              const msgs = [...c.messages];
              const last = { ...msgs[msgs.length - 1] };
              last.content += data.content;
              msgs[msgs.length - 1] = last;
              return { ...c, messages: msgs };
            });
          }
        }
      }
    } catch (err) {
      onUpdateChat((c) => {
        const msgs = [...c.messages];
        const last = { ...msgs[msgs.length - 1] };
        last.content = `Error: ${err.message}`;
        last.isStreaming = false;
        msgs[msgs.length - 1] = last;
        return { ...c, messages: msgs };
      });
    }

    // Mark streaming done
    onUpdateChat((c) => {
      const msgs = [...c.messages];
      const last = { ...msgs[msgs.length - 1] };
      last.isStreaming = false;
      msgs[msgs.length - 1] = last;
      return { ...c, messages: msgs };
    });

    setIsStreaming(false);
  };

  // ── Empty state ──
  if (!chat) {
    return (
      <main className="playground">
        <div className="playground-empty">
          <h1>Agentic Chatbot</h1>
          <p>Start a new conversation to begin</p>
          <button className="start-btn" onClick={onNewChat}>
            New Chat
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="playground">
      <div className="messages-area">
        {chat.messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <div className="input-form">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Tulis pesan..."
            rows={1}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            Kirim
          </button>
        </div>
      </div>
    </main>
  );
}

function MessageBubble({ message }) {
  const [thinkCollapsed, setThinkCollapsed] = useState(false);

  if (message.role === "user") {
    return <div className="message user">{message.content}</div>;
  }

  const hasThinking = message.thinking && message.thinking.length > 0;
  const hasContent = message.content && message.content.length > 0;

  // Streaming with nothing yet — show typing indicator
  if (message.isStreaming && !hasThinking && !hasContent) {
    return (
      <div className="message assistant">
        <div className="typing-indicator">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
      </div>
    );
  }

  // Auto-collapse thinking once content starts
  const collapsed = hasContent && !message.isStreaming ? thinkCollapsed : false;

  return (
    <div className="message assistant">
      {hasThinking && (
        <div
          className={`thinking-block ${collapsed ? "collapsed" : ""} ${
            !hasContent ? "only" : ""
          }`}
        >
          <div
            className="thinking-header"
            onClick={() => hasContent && setThinkCollapsed((v) => !v)}
          >
            <span className="arrow">&#9660;</span>
            {message.isStreaming && !hasContent ? "Thinking..." : "Thought process"}
          </div>
          <div className="thinking-content">{message.thinking}</div>
        </div>
      )}
      {hasContent && (
        <div className={`content-block ${!hasThinking ? "only" : ""}`}>
          {message.content}
        </div>
      )}
    </div>
  );
}
