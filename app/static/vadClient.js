function float32ArrayToWavBlob(samples, sampleRate = 16000) {
        const buffer = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(buffer);

        function writeString(view, offset, string) {
            for (let i = 0; i < string.length; i++) {
                view.setUint8(offset + i, string.charCodeAt(i));
            }
        }

        writeString(view, 0, 'RIFF');
        view.setUint32(4, 36 + samples.length * 2, true);
        writeString(view, 8, 'WAVE');
        writeString(view, 12, 'fmt ');
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, sampleRate, true);
        view.setUint32(28, sampleRate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(view, 36, 'data');
        view.setUint32(40, samples.length * 2, true);

        let offset = 44;
        for (let i = 0; i < samples.length; i++, offset += 2) {
            let s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }

        return new Blob([view], { type: 'audio/wav' });
}
function sendAudioToPython(socket,blob) {

    if (socket.state() === WebSocket.OPEN) {
        socket.send(blob); // Sends the raw audio chunk instantly
    } else {
        console.warn("WebSocket is not open yet.");
    }
}
export class VAD{
    constructor({
        socket,
        onSpeechEnd = null,
        onSpeechStart = null,
        onVADReady = null,
        onVADStop = null,
    } = {}) {
        this.onSpeedend = onSpeechEnd;
        this.onSpeechStart = onSpeechStart;
        this.onVADReady = onVADReady; // Hook to pass data back to your UI/app
        this.onVADStop = onVADStop;
        this.socket = socket;
        this.myVad = null;
    }
    async start(){
        try {
            if(this.myVad === null){
                console.log("VAD initialization triggered!");

                // Initialize client-side browser VAD using @ricky0123/vad-web
                this.myVad = await vad.MicVAD.new({
                    baseAssetPath: "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@latest/dist/",
                    onnxWASMBasePath: "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/",
                    onSpeechStart: () => {
                        console.log("🗣️ Speech started detected in browser!");
                        return this.onSpeechStart?.();
                    },
                    onSpeechEnd: async (audio) => {
                        console.log("🤫 Speech ended, audio chunk ready:", audio);
                        // You can send this audio chunk to Python via Gradio API or process it locally
                        const wavBlob = float32ArrayToWavBlob(audio, 16000);
                        // Send the WAV blob to the stt server
                        await sendAudioToPython(this.socket,wavBlob);
                        return this.onSpeechEnd?.(wavBlob);
                    },
                    onVADReady: () => {
                        console.log("✅ VAD is ready and listening to mic!");
                        alert("Microphone connected to browser VAD!");
                        return this.onVADReady?.();
                    }
                });
                this.socket.connect();
                this.myVad.start();
            }
            
        } catch (error) {
            console.error("Failed to start VAD:", error);
            alert({error});
        }
    }
    async stop(){
        try{
            if(this.myVad !== null){
                // Stop and completely cleanup the microphone stream and model instance
                console.log("Stopping VAD...");
                this.socket.stop();
                this.myVad.destroy(); 
                this.myVad = null;
                //trigger display text to chat box
                return this.onVADStop?.();
            }
            
            console.log("🛑 VAD stopped and resources released.");
        }
        catch(error){
            console.error("Failed to start VAD:", error);
            alert(error);
        }
    }

}