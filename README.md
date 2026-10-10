# LocalChatAgent

Local Chat Agent - Docker-based Python web server using Nicegui

What App Do:
    Run a local webserver using Nicegui
    Support chat to backend Ollama LLM qwen2.5:3b -> Docker container
    Support STT using parakeet -> Docker container
    Support TTS using kokoro -> Docker container
    The Voice chunk recongine lying on client side using onnxruntime-web and vad-web

0. Make sure docker is installed on your local enviroment

1. Build the docker images
note: below cmd run on folder content docker-compose.yaml

```cmd
docker compose build --no-cache
```
It will build 3 images: kokoro , parakeet, ollama

2. Up the container
```cmd
docker compose up -d
```
Note: Event the container was up using docker logs to check the status of it because it still need load AI models.
Note: kokoro and parakeet have /health API to check it online or not.

3. Run the local Web server and client app 

```cmd
cd ./app
python ./main.py
```
Note: this app using Nicegui