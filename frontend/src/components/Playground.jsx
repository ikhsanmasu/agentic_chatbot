import { useState, useRef, useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "";
const USER_ID = "0";

export default function Playground({ chat, messages, setMessages, onUpdateChat, onNewChat }) {
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

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

    const isFirstMessage = messages.length === 0;

    const userMsg = { role: "user", content: text };
    const assistantMsg = {
      role: "assistant",
      content: "",
      thinking: "",
      isStreaming: true,
      thinkingDone: false,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // Update title in sidebar immediately for first message
    if (isFirstMessage) {
      onUpdateChat(() => ({ title: text.slice(0, 40) }));
    }

    let fullContent = "";
    let fullThinking = "";

    // Build history from existing messages (exclude the ones we just added)
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .filter((m) => m.content && m.content.length > 0)
      .map((m) => ({ role: m.role, content: m.content }));

    try {
      const response = await fetch(`${API_BASE}/v1/chatbot/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
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
            fullThinking += data.content;
            setMessages((prev) => {
              const msgs = [...prev];
              const last = { ...msgs[msgs.length - 1] };
              last.thinking += data.content;
              msgs[msgs.length - 1] = last;
              return msgs;
            });
          }

          if (data.type === "content") {
            fullContent += data.content;
            setMessages((prev) => {
              const msgs = [...prev];
              const last = { ...msgs[msgs.length - 1] };
              if (!last.thinkingDone && last.thinking) {
                last.thinkingDone = true;
              }
              last.content += data.content;
              msgs[msgs.length - 1] = last;
              return msgs;
            });
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const msgs = [...prev];
        const last = { ...msgs[msgs.length - 1] };
        last.content = `Error: ${err.message}`;
        last.isStreaming = false;
        msgs[msgs.length - 1] = last;
        return msgs;
      });
      setIsStreaming(false);
      return;
    }

    // Mark streaming done
    setMessages((prev) => {
      const msgs = [...prev];
      const last = { ...msgs[msgs.length - 1] };
      last.isStreaming = false;
      last.thinkingDone = true;
      msgs[msgs.length - 1] = last;
      return msgs;
    });

    setIsStreaming(false);

    // Save messages to backend
    try {
      await fetch(
        `${API_BASE}/v1/chatbot/conversations/${USER_ID}/${chat.id}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_message: text,
            assistant_content: fullContent,
            assistant_thinking: fullThinking || null,
          }),
        }
      );
    } catch {
      // ignore save errors
    }

    // Update title on first message
    if (isFirstMessage) {
      const title = text.slice(0, 40);
      try {
        await fetch(
          `${API_BASE}/v1/chatbot/conversations/${USER_ID}/${chat.id}/title`,
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
          }
        );
      } catch {
        // ignore title update errors
      }
    }
  };

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
        {messages.map((msg, i) => (
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
  const [collapsed, setCollapsed] = useState(false);

  if (message.role === "user") {
    return <div className="message user">{message.content}</div>;
  }

  const hasThinking = message.thinking && message.thinking.length > 0;
  const hasContent = message.content && message.content.length > 0;
  const isThinkingActive = message.isStreaming && !message.thinkingDone;

  // Streaming with nothing yet
  if (message.isStreaming && !hasThinking && !hasContent) {
    return (
      <div className="message assistant">
        <div className="thinking-block active">
          <div className="thinking-header">
            <ThinkingSpinner />
            <span>Thinking...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message assistant">
      {hasThinking && (
        <div
          className={`thinking-block ${isThinkingActive ? "active" : ""} ${
            collapsed ? "collapsed" : ""
          } ${!hasContent ? "only" : ""}`}
        >
          <div
            className="thinking-header"
            onClick={() => !isThinkingActive && setCollapsed((v) => !v)}
          >
            {isThinkingActive ? (
              <ThinkingSpinner />
            ) : (
              <span className={`arrow ${collapsed ? "right" : ""}`}>
                &#9660;
              </span>
            )}
            <span>
              {isThinkingActive ? "Thinking..." : "Thought process"}
            </span>
          </div>
          {!collapsed && (
            <div className="thinking-content">
              <ThinkingSteps text={message.thinking} isActive={isThinkingActive} />
            </div>
          )}
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

function ThinkingSpinner() {
  return (
    <span className="thinking-spinner">
      <span className="spinner-dot" />
      <span className="spinner-dot" />
      <span className="spinner-dot" />
    </span>
  );
}

function ThinkingSteps({ text, isActive }) {
  const lines = text.split("\n").filter((l) => l.trim() !== "");

  return (
    <div className="thinking-steps">
      {lines.map((line, i) => {
        const isLast = i === lines.length - 1;
        const isStep = isStepLine(line);
        const isError = isErrorLine(line);
        const isSql = line.startsWith("SQL:");

        let cls = "step-line";
        if (isError) cls += " step-error";
        else if (isSql) cls += " step-sql";
        else if (isStep) cls += " step-action";

        return (
          <div key={i} className={cls}>
            {isStep && (
              <span className="step-indicator">
                {isActive && isLast ? (
                  <span className="step-pulse" />
                ) : isError ? (
                  <span className="step-icon error">!</span>
                ) : (
                  <span className="step-icon done">&#10003;</span>
                )}
              </span>
            )}
            <span className="step-text">{line}</span>
          </div>
        );
      })}
    </div>
  );
}

function isStepLine(line) {
  const steps = [
    "Routing to:",
    "Introspecting",
    "Found ",
    "Generating SQL",
    "Validating",
    "Executing query",
    "Query returned",
    "Synthesizing",
    "Retrying",
    "Reasoning:",
  ];
  return steps.some((s) => line.startsWith(s));
}

function isErrorLine(line) {
  return (
    line.startsWith("Parse error:") ||
    line.startsWith("Validation failed:") ||
    line.startsWith("Execution error:") ||
    line.startsWith("Error:")
  );
}
