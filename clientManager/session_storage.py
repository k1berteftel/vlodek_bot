from pyrogram import Client


class ClientManager():
    def __init__(self):
        self.manager: dict[int, Client] = {}

    async def add_client(self, user_id: int, client: Client):
        await self.clear_client(user_id)
        self.manager[user_id] = client

    async def clear_client(self, user_id: int):
        client = self.manager.get(user_id)
        if client:
            try:
                await client.stop()
            except Exception:
                ...
            del self.manager[user_id]

