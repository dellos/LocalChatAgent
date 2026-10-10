from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import torch
import soundfile as sf
import io
import base64
from kokoro import KPipeline
import asyncio
import threading
from typing import AsyncIterator, Iterator

app = FastAPI(title="Kokoro TTS API", description="FastAPI wrapper for Kokoro-82M")
_SENTINEL = object() #using to check on multithred which read only
# Initialize pipeline (defaulting to American English 'a', change if needed)
# Languages: 'a' (US), 'b' (GB), 'e' (Español), 'f' (Français), etc.
pipeline = KPipeline(lang_code='a')

class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"  # Default voice
    speed: float = 1.0
def process_tts(text,voice,speed):
    results = []
    # Run the generator to yield chunks dynamically
    generator = pipeline(
        text, 
        voice=voice, 
        speed=speed, 
        split_pattern=r'\n+'
    )
    for i, (gs, ps, audio) in enumerate(generator):
        # gs: graphemes (the text chunk segment)
        # ps: phonemes
        # audio: torch tensor of audio samples (24000Hz)
        
        if audio is None or len(audio) == 0:
            continue

        # Convert audio tensor to WAV bytes in-memory
        buffer = io.BytesIO()
        # Ensure audio is a numpy array
        audio_np = audio.numpy() if isinstance(audio, torch.Tensor) else audio
        sf.write(buffer, audio_np, 24000, format='WAV')
        buffer.seek(0)
        
        audio_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        results.append({
                    "chunk_index": i,
                    "text": gs,
                    "phonemes": ps,
                    "audio_base64": audio_base64
                })
    return results
async def process_tts_on_background(text,voice,speed):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None,lambda: process_tts(text,voice,speed))

def process_tts_chunk(text,voice,speed) -> Iterator:
    # Run the generator to yield chunks dynamically
    generator = pipeline(
        text, 
        voice=voice, 
        speed=speed, 
        split_pattern=r'(?<=[.!?])\s+|\n+'
    )
    for i, (gs, ps, audio) in enumerate(generator):
        # gs: graphemes (the text chunk segment)
        # ps: phonemes
        # audio: torch tensor of audio samples (24000Hz)
        
        if audio is None or len(audio) == 0:
            continue

        # Convert audio tensor to WAV bytes in-memory
        buffer = io.BytesIO()
        # Ensure audio is a numpy array
        audio_np = audio.numpy() if isinstance(audio, torch.Tensor) else audio
        sf.write(buffer, audio_np, 24000, format='WAV')
        buffer.seek(0)
        
        audio_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        yield {
            "chunk_index": i,
            "text": gs,
            "phonemes": ps,
            "audio_base64": audio_base64
        }

async def stream_from_thread(long_run,maxsize = 8) -> AsyncIterator:
    loop = asyncio.get_event_loop()
    queue = asyncio.Queue(maxsize=maxsize)
    stop = threading.Event()
    def worker():
        try:
            for chunk in long_run():
                if stop.is_set():
                    break
                # block this thread until the loop has room in the queue
                asyncio.run_coroutine_threadsafe(queue.put(chunk), loop).result()
        except BaseException as e:
            asyncio.run_coroutine_threadsafe(queue.put(e), loop).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(_SENTINEL), loop).result()
    # Run the generator to yield chunks dynamically
    task = loop.run_in_executor(None,worker)
    try:
        while True:
            item = await queue.get()
            if item == _SENTINEL:
                break
            if isinstance(item, BaseException): #queue.put(e)
                raise item 
            yield item
    finally:
        stop.set() #incase of go here before worker(which on background thread) end 
        while not queue.empty():
            queue.get_nowait()
        await task #await for worker thread end.
    


 
@app.websocket("/api/tts")
async def websocket_synthesize(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Expecting JSON input from the client: {"text": "...", "voice": "af_heart", "speed": 1.0}
            data = await websocket.receive_json()
            text = data.get("text", "")
            voice = data.get("voice", "af_heart")
            speed = float(data.get("speed", 1.0))

            #TODO: may be no need to close
            if not text:
                await websocket.send_json({"error": "Text field is required."}) 
                await websocket.close()
                return
           
            # dat = await process_tts_on_background(text,voice,speed)
            # await websocket.send_json({
            #     "dat" : dat
            # })
            async for chunk in stream_from_thread(lambda: process_tts_chunk(text=text,voice=voice,speed=speed)):
                await websocket.send_json(chunk) 

            # Send completion signal
            await websocket.send_json({"status": "completed"})

    except WebSocketDisconnect:
        print("Client disconnected from WebSocket stream.")
    except Exception as e:
        await websocket.send_json({"error": str(e)})
        await websocket.close()

@app.post("/synthesize")
async def synthesize_speech(data: TTSRequest):
    try:
        generator = pipeline(
            data.text, 
            voice=data.voice, 
            speed=data.speed, 
            split_pattern=r'\n+'
        )
        
        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)
            
        if not audio_chunks:
            raise HTTPException(status_code=400, detail="Audio generation failed.")
            
        # Concatenate chunks
        full_audio = torch.cat([torch.tensor(chunk) for chunk in audio_chunks])
        
        # Save to an in-memory WAV buffer
        buffer = io.BytesIO()
        sf.write(buffer, full_audio.numpy(), 24000, format='WAV')
        buffer.seek(0)
        
        encoded_audio = base64.b64encode(buffer.read()).decode('utf-8')
        
        return {
            "status": "success",
            "voice": data.voice,
            "audio_base64": encoded_audio
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str.__(e) if hasattr(e, '__') else str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

