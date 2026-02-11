import { useState, useCallback, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Playground from "./components/Playground";

const API_BASE = import.meta.env.VITE_API_URL || "";
const USER_ID = "0";

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [activeMessages, setActiveMessages] = useState([]);

  // Load conversation list on mount
  useEffect(() => {
    fetch(`${API_BASE}/v1/chatbot/conversations/${USER_ID}`)
      .then((r) => r.json())
      .then((data) => setChats(data))
      .catch(() => {});
  }, []);

  const createNewChat = useCallback(async () => {
    try {
      const res = await fetch(
        `${API_BASE}/v1/chatbot/conversations/${USER_ID}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: "New Chat" }),
        }
      );
      const conv = await res.json();
      setChats((prev) => [conv, ...prev]);
      setActiveChatId(conv.id);
      setActiveMessages([]);
    } catch {
      // fallback: local-only chat
      const id = Date.now().toString();
      setChats((prev) => [{ id, title: "New Chat" }, ...prev]);
      setActiveChatId(id);
      setActiveMessages([]);
    }
  }, []);

  const selectChat = useCallback(
    async (chatId) => {
      setActiveChatId(chatId);
      try {
        const res = await fetch(
          `${API_BASE}/v1/chatbot/conversations/${USER_ID}/${chatId}`
        );
        const data = await res.json();
        setActiveMessages(data.messages || []);
      } catch {
        setActiveMessages([]);
      }
    },
    []
  );

  const deleteChat = useCallback(
    async (chatId) => {
      try {
        await fetch(
          `${API_BASE}/v1/chatbot/conversations/${USER_ID}/${chatId}`,
          { method: "DELETE" }
        );
      } catch {
        // ignore
      }
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (activeChatId === chatId) {
        setActiveChatId(null);
        setActiveMessages([]);
      }
    },
    [activeChatId]
  );

  const updateChat = useCallback((chatId, updater) => {
    setChats((prev) =>
      prev.map((c) => (c.id === chatId ? { ...c, ...updater(c) } : c))
    );
  }, []);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={selectChat}
        onNewChat={createNewChat}
        onDeleteChat={deleteChat}
      />
      <Playground
        chat={activeChat}
        messages={activeMessages}
        setMessages={setActiveMessages}
        onUpdateChat={(updater) =>
          activeChatId && updateChat(activeChatId, updater)
        }
        onNewChat={createNewChat}
      />
    </div>
  );
}
