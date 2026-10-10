FROM ollama/ollama:latest

ENV OLLAMA_HOST=0.0.0.0:11434

RUN ollama serve & \
    sleep 5 && \
    ollama pull qwen2.5:3b && \
    pkill ollama

EXPOSE 11434

ENTRYPOINT ["ollama", "serve"]