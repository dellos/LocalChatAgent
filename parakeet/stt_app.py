from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from transformers import pipeline
import soundfile as sf
import io

app = FastAPI(title="Parakeet STT API", description="FastAPI wrapper for parakeet-ctc-1.1b")

print("Loading local Parakeet model...")
ASR_PIPE = pipeline("automatic-speech-recognition", model="nvidia/parakeet-ctc-1.1b")
print("Model loaded successfully!")
async def process_stream_file_to_text(audio_chunk):
    if audio_chunk is None:
        return ""
    # 3. Run the blocking Hugging Face pipeline in a separate background thread.
    # This prevents the heavy CPU/GPU inference from blocking your async server loop.
    try:
        # Note: Depending on how your audio_chunk is formatted, 
        # the pipeline usually expects a file path, a numpy array, or bytes.
        data, samplerate = sf.read(io.BytesIO(audio_chunk))
        #TODO: check here , about asyncio loop
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: ASR_PIPE({"array": data, "sampling_rate": samplerate}) #this one using for hf model
            # lambda: asr_pipe.transcribe(audio=[data], batch_size=1)
        )
        
        return result.get("text", "")
        # return result[0]
    except Exception as e:
        print(f"Transcription error: {e}")
        return ""
    
#api to get audio from client, create new websocket instead of using app.post
#may need to using background task to return 
#TODO: check that every client conect to this api will create it own process. 
@app.websocket('/ws/stt')
async def audio_to_text(websocket: WebSocket):
    await websocket.accept()
    print("Custom WebSocket client connected!")
    try:
        while True:
            # Receive data chunk or text from JS client
            chunk_bytes = await websocket.receive_bytes()
            text = await process_stream_file_to_text(chunk_bytes)
            print(f"user text: {text}")
            # Send data back 
            # await websocket.send_text(f"Acknowledged chunk: {data}")
            #Send data back to connected client 
            await websocket.send_text(f"{text}")    
    except WebSocketDisconnect:
        print("Custom WebSocket client disconnected")

@app.get('/api/health')
def health_check():
    return {"status": "healthy"}