import json
import time
import uuid

import redis

MAX_CONVERSATIONS = 20


class ChatRepository:
    def __init__(self, r: redis.Redis):
        self.r = r

    def _conv_set_key(self, user_id: str) -> str:
        return f"user:{user_id}:conversations"

    def _conv_hash_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}"

    def _conv_messages_key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}:messages"

    def create_conversation(self, user_id: str, title: str = "New Chat") -> dict:
        conversation_id = str(uuid.uuid4())
        now = time.time()

        conv = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

        pipe = self.r.pipeline()
        pipe.hset(self._conv_hash_key(conversation_id), mapping={k: str(v) for k, v in conv.items()})
        pipe.zadd(self._conv_set_key(user_id), {conversation_id: now})
        pipe.execute()

        self._enforce_max_conversations(user_id)

        return conv

    def list_conversations(self, user_id: str) -> list[dict]:
        conv_ids = self.r.zrevrange(self._conv_set_key(user_id), 0, -1)
        conversations = []
        for cid in conv_ids:
            data = self.r.hgetall(self._conv_hash_key(cid))
            if data:
                data["created_at"] = float(data["created_at"])
                data["updated_at"] = float(data["updated_at"])
                conversations.append(data)
        return conversations

    def get_conversation(self, conversation_id: str) -> dict | None:
        data = self.r.hgetall(self._conv_hash_key(conversation_id))
        if not data:
            return None

        data["created_at"] = float(data["created_at"])
        data["updated_at"] = float(data["updated_at"])

        raw_messages = self.r.lrange(self._conv_messages_key(conversation_id), 0, -1)
        data["messages"] = [json.loads(m) for m in raw_messages]

        return data

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        existed = self.r.exists(self._conv_hash_key(conversation_id))
        if not existed:
            return False

        pipe = self.r.pipeline()
        pipe.delete(self._conv_hash_key(conversation_id))
        pipe.delete(self._conv_messages_key(conversation_id))
        pipe.zrem(self._conv_set_key(user_id), conversation_id)
        pipe.execute()

        return True

    def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        if not self.r.exists(self._conv_hash_key(conversation_id)):
            return False

        now = time.time()
        self.r.hset(self._conv_hash_key(conversation_id), mapping={
            "title": title,
            "updated_at": str(now),
        })

        user_id = self.r.hget(self._conv_hash_key(conversation_id), "user_id")
        if user_id:
            self.r.zadd(self._conv_set_key(user_id), {conversation_id: now})

        return True

    def save_messages(
        self,
        conversation_id: str,
        user_message: str,
        assistant_content: str,
        assistant_thinking: str | None = None,
    ) -> bool:
        if not self.r.exists(self._conv_hash_key(conversation_id)):
            return False

        user_msg = {"role": "user", "content": user_message}
        assistant_msg = {"role": "assistant", "content": assistant_content}
        if assistant_thinking:
            assistant_msg["thinking"] = assistant_thinking

        pipe = self.r.pipeline()
        pipe.rpush(self._conv_messages_key(conversation_id), json.dumps(user_msg))
        pipe.rpush(self._conv_messages_key(conversation_id), json.dumps(assistant_msg))

        now = time.time()
        pipe.hset(self._conv_hash_key(conversation_id), "updated_at", str(now))

        user_id = self.r.hget(self._conv_hash_key(conversation_id), "user_id")
        if user_id:
            pipe.zadd(self._conv_set_key(user_id), {conversation_id: now})

        pipe.execute()

        return True

    def _enforce_max_conversations(self, user_id: str):
        key = self._conv_set_key(user_id)
        count = self.r.zcard(key)
        if count <= MAX_CONVERSATIONS:
            return

        to_remove = self.r.zrange(key, 0, count - MAX_CONVERSATIONS - 1)
        pipe = self.r.pipeline()
        for cid in to_remove:
            pipe.delete(self._conv_hash_key(cid))
            pipe.delete(self._conv_messages_key(cid))
        pipe.zremrangebyrank(key, 0, count - MAX_CONVERSATIONS - 1)
        pipe.execute()
