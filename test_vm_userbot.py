import asyncio
from telethon import TelegramClient, events

client = TelegramClient('./tg', 2040, 'b18441a1ff607e10a989891a5462e627')

async def main():
    await client.start()
    me = await client.get_me()
    print(f'me: {me.first_name} id={me.id}', flush=True)

    @client.on(events.NewMessage(incoming=True))
    async def h(event):
        print(f'MSG: {event.text} from={event.sender_id}', flush=True)
        await event.respond('vm test reply')

    # Force update state sync
    dialogs = await client.get_dialogs(limit=10)
    print(f'dialogs: {len(dialogs)}', flush=True)
    await client.catch_up()
    print('caught up, waiting for messages...', flush=True)
    await client.run_until_disconnected()

asyncio.run(main())
