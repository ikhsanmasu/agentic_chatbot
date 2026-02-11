export default function Sidebar({ chats, activeChatId, onSelectChat, onNewChat, onDeleteChat }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Playground</h2>
        <button className="new-chat-btn" onClick={onNewChat}>
          + New Chat
        </button>
      </div>
      <div className="chat-list">
        {chats.map((chat) => (
          <div
            key={chat.id}
            className={`chat-item ${chat.id === activeChatId ? "active" : ""}`}
            onClick={() => onSelectChat(chat.id)}
          >
            <span className="chat-item-title">{chat.title}</span>
            <button
              className="chat-delete-btn"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteChat(chat.id);
              }}
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}
