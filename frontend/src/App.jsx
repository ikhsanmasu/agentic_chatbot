import { useState, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Playground from "./components/Playground";

export default function App() {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);

  const createNewChat = useCallback(() => {
    const newChat = {
      id: Date.now().toString(),
      title: "New Chat",
      messages: [],
    };
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
  }, []);

  const updateChat = useCallback((chatId, updater) => {
    setChats((prev) =>
      prev.map((c) => (c.id === chatId ? updater(c) : c))
    );
  }, []);

  const activeChat = chats.find((c) => c.id === activeChatId) || null;

  return (
    <div className="app">
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={setActiveChatId}
        onNewChat={createNewChat}
      />
      <Playground
        chat={activeChat}
        onUpdateChat={(updater) =>
          activeChatId && updateChat(activeChatId, updater)
        }
        onNewChat={createNewChat}
      />
    </div>
  );
}
