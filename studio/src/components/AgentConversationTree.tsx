import React from "react";
import { AgentConversationMessage } from "../api/types";

interface AgentConversationTreeProps {
  messages: AgentConversationMessage[];
  selectedMessageId: string | null;
  onSelectMessage: (id: string) => void;
}

const AgentConversationTree: React.FC<AgentConversationTreeProps> = ({ messages, selectedMessageId, onSelectMessage }) => {
  if (!messages || messages.length === 0) {
    return <div className="empty-state">No conversation captured.</div>;
  }
  return (
    <div className="conversation-tree">
      <h4>Conversation</h4>
      <ul>
        {messages.map((msg) => (
          <li
            key={msg.id}
            className={selectedMessageId === msg.id ? "active" : ""}
            onClick={() => onSelectMessage(msg.id)}
          >
            <div className="message-role">{msg.role}</div>
            <div className="message-content">{msg.content_preview}</div>
            <div className="message-meta">{new Date(msg.timestamp).toLocaleTimeString()}</div>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default AgentConversationTree;
