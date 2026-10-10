export class AudioWebSocket {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.onMessageCallback = null; // Hook to pass data back to your UI/app
    }
    
    connect() {
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            console.log("Connected to Python backend WebSocket!");
        };

        this.socket.onmessage = async (event) => {
            console.log("Response from Python:", event.data);
            
            // If a callback was registered, trigger it with the incoming data
            if (this.onMessageCallback) {
                await this.onMessageCallback(event.data);
            }
        };

        this.socket.onclose = () => {
            console.log("WebSocket disconnected.");
        };

        this.socket.onerror = (error) => {
            console.error("WebSocket error:", error);
        };
    }
    stop(){
        this.socket.close();
        console.log("WebSocket Closed");
    }
    state(){
        return this.socket.readyState;
    }
    // Method to send messages to Python
    send(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(data);
        } else {
            console.warn("WebSocket is not open. Unable to send data.");
        }
    }

    // Allow your main app to register what happens when a message arrives
    onMessage(callback) {
        this.onMessageCallback = callback;
    }
}