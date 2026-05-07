const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const chatLauncher = document.getElementById('chat-launcher');
const chatWidget = document.getElementById('chat-widget');
const closeChat = document.getElementById('close-chat');
const clearChat = document.getElementById('clear-chat');
const actionChips = document.querySelectorAll('.action-chip');

const API_URL = 'http://127.0.0.1:8000/chat';
const VOICE_API_URL = 'http://127.0.0.1:8000/chat/voice';

let mediaRecorder;
let audioChunks = [];
let isRecording = false;

// Removed filler audio logic as files are missing
let currentAudio = null;

// Launcher Toggle
chatLauncher.addEventListener('click', () => {
    const isActive = chatWidget.classList.toggle('hidden');
    chatLauncher.classList.toggle('active', !isActive);
});

closeChat.addEventListener('click', () => {
    chatWidget.classList.add('hidden');
    chatLauncher.classList.remove('active');
});

clearChat.addEventListener('click', () => {
    if (confirm('Are you sure you want to delete the chat history?')) {
        const welcome = document.querySelector('.welcome-section');
        chatContainer.innerHTML = '';
        chatContainer.appendChild(welcome);
    }
});

// Quick Action Chips
actionChips.forEach(chip => {
    chip.addEventListener('click', () => {
        const query = chip.getAttribute('data-query');
        userInput.value = query;
        handleSendMessage();
    });
});

function appendMessage(message, isBot = false, sources = []) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isBot ? 'bot-message' : 'user-message'} fade-in`;
    
    let content = isBot ? marked.parse(message) : `<p>${message}</p>`;
    
    if (isBot && sources.length > 0) {
        content += '<div class="sources">';
        const uniqueSources = [...new Set(sources)];
        uniqueSources.slice(0, 2).forEach(src => {
            content += `<a href="${src}" target="_blank" class="source-link">🔗 Learn more</a>`;
        });
        content += '</div>';
    }
    
    msgDiv.innerHTML = content;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot-message fade-in loading-item';
    loadingDiv.id = 'loading';
    loadingDiv.innerHTML = '<div class="loading-dots"><span></span><span></span><span></span></div>';
    chatContainer.appendChild(loadingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeLoading() {
    const loading = document.getElementById('loading');
    if (loading) loading.remove();
}

async function handleSendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, false);
    userInput.value = '';

    showLoading();

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000);

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();
        removeLoading();
        
        if (data.response) {
            appendMessage(data.response, true, data.sources);
        } else {
            appendMessage("I'm sorry, I couldn't retrieve that information.", true);
        }
    } catch (error) {
        console.error('Error:', error);
        removeLoading();
        appendMessage("The server is currently busy. Please try again in a few seconds.", true);
    }
}

sendBtn.addEventListener('click', handleSendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSendMessage();
});

// Voice Logic
const voiceOverlay = document.getElementById('voice-overlay');
const closeVoiceBtn = document.getElementById('close-voice-btn');
const voiceOrb = document.getElementById('voice-orb');
const voiceStatus = document.getElementById('voice-status');
const voiceSubtext = document.getElementById('voice-subtext');

function setVoiceState(state, statusText, subText) {
    voiceOrb.className = state;
    if (voiceStatus) voiceStatus.innerText = statusText;
    if (voiceSubtext) voiceSubtext.innerText = subText;
}

micBtn.addEventListener('click', () => {
    voiceOverlay.classList.remove('hidden');
    setVoiceState('idle', 'Voice Mode', 'Tap the orb to start speaking.');
});

closeVoiceBtn.addEventListener('click', () => {
    voiceOverlay.classList.add('hidden');
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
});

voiceOrb.addEventListener('click', async () => {
    if (voiceOrb.classList.contains('idle') || voiceOrb.classList.contains('speaking')) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.addEventListener("dataavailable", event => {
                audioChunks.push(event.data);
            });
            
            mediaRecorder.addEventListener("stop", async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                sendVoiceMessage(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            });
            
            mediaRecorder.start();
            setVoiceState('listening', 'Listening...', 'Speak now...');
            
            // Auto stop after 5 seconds for simplicity in this version
            setTimeout(() => {
                if (mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                    setVoiceState('thinking', 'Processing...', 'Thinking...');
                }
            }, 5000);
            
        } catch (err) {
            console.error("Mic error:", err);
            setVoiceState('idle', 'Error', 'Mic access denied.');
        }
    }
});

async function sendVoiceMessage(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'record.webm');
    
    try {
        const response = await fetch(VOICE_API_URL, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        
        const data = await response.json();
        
        if (data.user_query) appendMessage(data.user_query, false);
        if (data.response) appendMessage(data.response, true, data.sources);
        
        if (data.audio_url) {
            setVoiceState('speaking', 'Speaking...', 'Assistant is responding...');
            currentAudio = new Audio(data.audio_url);
            currentAudio.play();
            currentAudio.onended = () => {
                setVoiceState('idle', 'Voice Mode', 'Tap the orb to speak again.');
            };
        } else {
            setVoiceState('idle', 'Voice Mode', 'Tap the orb to speak again.');
        }
    } catch (error) {
        console.error('Voice Error:', error);
        setVoiceState('idle', 'Error', 'Voice processing failed.');
    }
}

