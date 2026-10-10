# LocalChatAgent

Local Chat Agent - Docker-based Python web server using Nicegui

## Run locally

1. Build the Docker image:
   ```bash
   docker build -t localchatagent .
   ```

2. Start the container:
   ```bash
   docker run -d -p 8080:8080 --name localchatagent localchatagent
   ```

3. Open the app in your browser:
   ```text
   http://localhost:8080
   ```

## Notes

- The app runs a local web server using NiceGUI.
- The container exposes port 8080 for access from your browser.
