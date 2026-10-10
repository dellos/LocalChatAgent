#!/usr/bin/env python3
from datetime import datetime
from uuid import uuid4
from ollama import AsyncClient
from nicegui import app, ui, Client, ElementFilter, context
from html_sanitizer import Sanitizer
from pydantic import BaseModel
from fastapi import FastAPI, Request
from pathlib import Path
import asyncio
import websockets
import json
import base64, io, wave
# Get the folder where main.py is currently located (app/)
current_dir = Path(__file__).parent

#this one shared among all users
messages: list[tuple[str, str, str, str,str]] = []
talking_dict: dict[str, str] = {}   # client_id -> {'text': 'accum'}

app.add_static_files('/static', f'{current_dir}/static')
BOT_ID  = str(uuid4())
BOT_AVATR = f'https://robohash.org/{BOT_ID}?bgset=bg2'
OLLAMA_URL = "http://localhost:1234"
KOKORO_TTS_URL = "ws://localhost:1235/api/tts"
MODEL = "qwen2.5:3b"
#DTO
class UpdatePayload(BaseModel):
    client_id: str
    text: str
#Model
class WSClient:
    def __init__(self, url: str):
        self.url = url
        self.ws = None
        self.lock = asyncio.Lock()   # stops two requests mixing replies, incase of using the object on multithread 

    async def connect(self):
        try:
            if self.ws == None:
                self.ws = await websockets.connect(self.url)
        except Exception as e:
            print(f"Websocket connection to server with error: {e}")
            #TODO: return failed message
    async def stream(self, text: str):
        """Yields each chunk dict as it arrives."""
        async with self.lock:
            assert self.ws is not None #TODO temp, need check and return message
            await self.ws.send(json.dumps({
                "text": text,
                "voice": "af_heart",
                "speed": 1.0
                }))
            while True:
                data = json.loads(await self.ws.recv())
                print("stream chunk")
                if data.get("status") == "completed":
                    return
                error = data.get("error")
                if error:
                    raise RuntimeError(error)
                dat = data.get("dat")
                if dat:
                    yield dat    
                else:
                    yield data
    async def request(self, text: str) -> list[dict]:
        await self.connect()
        """Waits for everything and returns all chunks."""
        return [ chunk async for chunk in self.stream(text)]
    
    # async def request(self, text: str) -> list[dict]:
    #     await self.connect()
    #     """Waits for everything and returns all chunks."""
    #     result = []
    #     async for chunk_list in self.stream(text):
    #         result.extend(chunk_list)
    #     return result
   
    async def close(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
def merge_wav_b64(chunks: list[dict]) -> str:
    out = io.BytesIO()
    with wave.open(out, "wb") as w_out:
        for i, c in enumerate(chunks):
            with wave.open(io.BytesIO(base64.b64decode(c["audio_base64"]))) as w_in:
                if i == 0:
                    w_out.setparams(w_in.getparams())
                w_out.writeframes(w_in.readframes(w_in.getnframes()))
    return base64.b64encode(out.getvalue()).decode()

#comunitaion to ollama which host llm
async def generate_response(message):
    client = AsyncClient(host=OLLAMA_URL)
    stream = await client.chat(
        model=MODEL,
        messages=message,
        stream=True
    )
    response = ''
    async for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)
        response += chunk["message"]["content"]
    return response

# send_to_tts_queue = asyncio.Queue() #all user using this queue to send but how to recied ??
# async def generate_vocie():
#     try:
#         while True:
#             with 
#     return response

#API region
#do find the right client then update it text box
#not using: due to we can update using js 
# @app.post('/api/update-textbox')
# def update_textbox_api(request: Request, payload: UpdatePayload):
#     # 1. Extract the browser's session cookie from the incoming request headers
#     # NiceGUI relies on standard session cookies to track storage.
#     # incoming_cookies = request.cookies
    
#     # 2. Find the exact client instance whose request shares the same cookies/session
#     target_client = Client.instances.get(payload.client_id)
#     # for c in Client.instances.values():
#     #     # Check if this active client's request cookies match the incoming API request cookies
#     #     if c.request and c.request.cookies.get('nicegui_session') == incoming_cookies.get('nicegui_session'):
#     #         target_client = c
#     #         break

#     # 3. Refresh only that specific user's chat box
#     if target_client:
#         with target_client:
#             current = talking_dict.get(payload.client_id, '')
#             talking_dict[payload.client_id] = f"{current} {payload.text}".strip()
#             chat_box.refresh(payload.client_id)
#             print(f"Successfully refreshed client: {target_client.id}")
#     return {"status": "success", "new_message": payload.text}

#ui region
async def send(e, own_id: str , avartar_id: str):
    own_id = ui.context.client.tab_id or ""
    avartar_id = app.storage.tab["avartar"]
    if e:
        await send_to(e.sender, own_id, avartar_id)
async def  send_to(box, own_id: str, avartar_id) -> None:
        user_id = own_id
        avatar = avartar_id
        stamp = datetime.now().strftime('%X')
        messages_text = box.value
        box.value = ''
        talking_dict[user_id] = ''
        if not messages_text:
            return
        messages.append((user_id,'user', avatar, messages_text, stamp))
        await chat_messages.refresh(user_id)
@ui.refreshable
async def chat_process_message(ai_voice_data, msg: str = ""):
    if msg:
        ui.chat_message(text= msg,avatar=BOT_AVATR, name='Bot', sent=False)
        ui.audio(f"data:audio/wav;base64,{merge_wav_b64(ai_voice_data)}", autoplay=True)
    else:
        ui.chat_message(avatar=BOT_AVATR, name='Bot', sent=False)
        ui.spinner(type='dots')
        
#.refresh() refreshes every client’s instance
#this mean if 2 tab open this below fn calling 2 times for one chat_messages.refresh(user_id)
@ui.refreshable
async def chat_messages(own_id:str) -> None:
    own_id = ui.context.client.tab_id or ""
    avartar_id = app.storage.tab["avartar"]
    tts_ws_client:WSClient|None = app.storage.client.get("tts",None)
    if messages:
            last_user_id = None
            request_messages = []
            for user_id, role, avatar, message, stamp in messages:
                last_user_id = user_id
                request_messages.append({
                    "role": role,
                    "content": message
                })
                ui.chat_message(text=message, name=role, stamp=stamp, avatar=avatar, sent=own_id == user_id)
            if last_user_id != BOT_ID:
                await chat_process_message(None)
                if last_user_id == own_id:
                    # response_message = ui.chat_message(avatar=BOT_AVATR, name='Bot', sent=False)
                    # spinner = ui.spinner(type='dots')
                    response = await generate_response(request_messages)
                    stamp = datetime.now().strftime('%X')
                    messages.append((BOT_ID,'bot', BOT_AVATR, response, stamp))
                    ai_voice_data = await tts_ws_client.request(response) if tts_ws_client else None
                    await chat_process_message.refresh(ai_voice_data, response)
                    # if tts_ws_client:
                    #     ai_voice_data = await tts_ws_client.request(response)
                        # ui.audio(f"data:audio/wav;base64,{merge_wav_b64(ai_voice_data)}", autoplay=True)
                    # spinner.delete()
                    # with response_message.clear():
                    #     ui.html(response, sanitize=Sanitizer().sanitize)
                
    else:
        ui.label('No messages yet').classes('mx-auto my-36')
    ui.run_javascript('window.scrollTo(0, document.body.scrollHeight)')
#chagne to using one way to source biniding to allow user change created text.
# @ui.refreshable
# async def chat_box(refresh_client_id:str, is_init:bool = False):
#     own_id = ui.context.client.tab_id or ""
#     client_id = ui.context.client.id or ""
#     avartar_id = app.storage.tab["avartar"]

#     #uisng chat-input mark to find and update by api
#     if is_init and client_id == refresh_client_id:
#         talking_dict[client_id] = ''
#         ui.input(placeholder='Your Message')\
#             .bind_value_to(talking_dict, client_id)\
#             .props('rounded outlined input-class=mx-3') \
#             .mark('chat-input').classes('w-full self-center')\
#             .on('keydown.enter', lambda e: send(e,own_id,avartar_id))
#     elif client_id == refresh_client_id:
#         current_message = talking_dict.get(client_id) or ""
#         ui.input(value=current_message)\
#             .bind_value_to(talking_dict, client_id)\
#             .props('rounded outlined input-class=mx-3') \
#             .mark('chat-input')\
#             .classes('w-full self-center')\
#             .on('keydown.enter', lambda e: send(e,own_id,avartar_id))

def update_chat_box(e,chat_box):
    # print(f"{e.args.get('id')}, {e.args.get('text')} , {chat_box.value}")
    chat_box.value = f'{chat_box.value or ""} {e.args["text"]}'.strip()

#NOTE: ui create inplace where this fn is calling.!!!
async def voice_chat_input(own_id,avartar_id):
    chat_box = ui.input('Message').classes('w-full').on('keydown.enter',lambda e: send(e,own_id,avartar_id))
    is_recording = False
    async def toggle(e):
        nonlocal is_recording
        ctrl_held = e.args.get('ctrlKey', False)
        is_recording = not is_recording
        e.sender.props(f'color={"red" if is_recording else "primary"}')
        e.sender.text = 'Recording' if is_recording else "Start"
        e.sender.classes(remove= 'bg-green-500' if is_recording else 'bg-red-500',
                        add='bg-green-500' if is_recording else 'bg-red-500')
        ui.run_javascript(f'recordToggle({chat_box.id},{is_recording})') # actualy no need id
        if ctrl_held and not is_recording:
           await send_to(chat_box,own_id,avartar_id)
        if not is_recording:
            spinner.set_visibility(False) 
    with ui.button('Start').on('click',lambda e:toggle(e)) as btn:
        spinner = ui.spinner(type='dots', size='sm').props('color=white')
        spinner.set_visibility(False)
    
    ui.on('stt_text',lambda e: update_chat_box(e,chat_box)) #custom event rise on js by using nicegui emitEvent
    ui.on('stt_process',lambda e: spinner.set_visibility(e.args.get('onProcess',False)))
    
#TODO: using Client.id will not presit cause new id will recreate if the tab reconnect to ws
@ui.page('/')
async def main(client: Client):
    tts_ws_client =  WSClient(KOKORO_TTS_URL)
    # Read the separate HTML file and inject it into the head
    ui.add_head_html(f'<script>window.clientId = "{client.id}";</script>')
    with open(f"{current_dir}/static/voice_componet.html", "r", encoding="utf-8") as f:
        html_content = f.read()
        ui.add_head_html(html_content)
    
    #note there 3 way to udpdate a textbox 
    #1 . attached js which have textbox id get here
    #2. move text box global. then it can update by api but need a dict to know what ui belong to who
    #3. using refeshable + app.storage
    client_id = client.id #str(uuid4()) #not using
 
    
    # app.storage.user['message'] = ''
    # app.storage.user['user_id'] = user_id #not using
    # app.storage.user['avatar'] = avartar
    app.storage.client["tts"] = tts_ws_client
    
    # async def voice_record(e,own_id,avartar_id):
    #     e.sender.is_running = not getattr(e.sender, 'is_running', False)
        
    #     if e.sender.is_running:
    #         ui.run_javascript('myvad.start()')
    #         e.sender.text = 'Stop'
    #         e.sender.classes(remove='bg-green-500', add='bg-red-500')
    #     else:
    #         ui.run_javascript('myvad.stop()')
    #         e.sender.text = 'Start'
    #         e.sender.classes(remove='bg-red-500', add='bg-green-500')
    #         e.sender.is_running = False
    #         box = next(iter(ElementFilter(kind=ui.input, marker='chat-input')), None)
    #         if box:
    #             await send_to(box,own_id,avartar_id)

    await ui.context.client.connected()  # chat_messages(...) uses run_javascript which is only possible after connecting
    own_id = ui.context.client.tab_id or ""
    avartar = f'https://robohash.org/{own_id}?bgset=bg2'
    app.storage.tab['avartar'] = avartar

    ui.add_css(r'a:link, a:visited {color: inherit !important; text-decoration: none; font-weight: 500}')
    with ui.footer().classes('bg-white'), ui.column().classes('w-full max-w-3xl mx-auto my-6'):
        with ui.row().classes('w-full no-wrap items-center'):
            with ui.avatar().on('click', lambda: ui.navigate.to(main)):
                ui.image(avartar)
            await voice_chat_input(own_id, avartar)
            # ui.button('record', icon='mic', on_click= lambda e: voice_record(e,own_id,avartar))
        ui.markdown('simple chat app built with [NiceGUI](https://nicegui.io)') \
            .classes('text-xs self-end mr-8 m-[-1em] text-primary')

    
    
    with ui.column().classes('w-full max-w-2xl mx-auto items-stretch') as message_container:
        await chat_messages(own_id)

    async def clean_up_client():
        talking_dict[client_id] = ''
        await tts_ws_client.close()

    client.on_disconnect(lambda:clean_up_client())
    client.on_exception(lambda:clean_up_client())
if __name__ in {'__main__', '__mp_main__'}:
    ui.run(storage_secret='mysecret_key',reload=False)