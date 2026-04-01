const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const micBtn = document.getElementById('mic-btn');
const clearChatBtn = document.getElementById('clear-chat-btn');
const suggestionChips = document.getElementById('suggestion-chips');
const chatToggleBtn = document.getElementById('chat-toggle-btn');
const appWrapper = document.getElementById('app-wrapper');
const minimizeBtn = document.getElementById('minimize-btn');

const API_URL = '/chat';
const VOICE_API_URL = '/chat/voice';

let mediaRecorder;
let audioChunks = [];
let isRecording = false;
const fillerAudios = [
    new Audio('filler1.wav'),
    new Audio('filler2.wav'),
    new Audio('filler3.wav')
];
let currentFillerAudio = null;
let currentAudio = null;
let chatStarted = false;

// Audio Visualization & Silence Detection Variables
let audioContext;
let analyser;
let microphone;
let animationId;
let hasSpoken = false;
let lastSpokeTime = 0;
const SILENCE_THRESHOLD = 15;
const SILENCE_DURATION = 2000;

const voiceOverlay = document.getElementById('voice-overlay');
const closeVoiceBtn = document.getElementById('close-voice-btn');
const voiceOrb = document.getElementById('voice-orb');
const voiceStatus = document.getElementById('voice-status');
const voiceSubtext = document.getElementById('voice-subtext');

// If this project is embedded as an iframe, respond to parent events.
window.addEventListener('message', (event) => {
    if (event.data === 'chat-maximized') {
        const appWrap = document.getElementById('app-wrapper');
        const input = document.getElementById('user-input');
        if (appWrap) appWrap.classList.remove('minimized');
        if (input) input.focus();
    } else if (event.data === 'chat-minimized') {
        const appWrap = document.getElementById('app-wrapper');
        if (appWrap) appWrap.classList.add('minimized');
    }
});

// --- Helper: Remove welcome section & chips on first message ---
function hideWelcome() {
    if (chatStarted) return;
    chatStarted = true;
    const welcome = document.querySelector('.welcome-section');
    const chips = document.getElementById('suggestion-chips');
    if (welcome) {
        welcome.style.opacity = '0';
        welcome.style.transform = 'translateY(-10px)';
        welcome.style.transition = 'all 0.3s ease';
        setTimeout(() => welcome.remove(), 300);
    }
    if (chips) {
        chips.style.opacity = '0';
        chips.style.transform = 'translateY(-10px)';
        chips.style.transition = 'all 0.3s ease';
        setTimeout(() => chips.remove(), 300);
    }
}

function appendMessage(message, isBot = false, sources = []) {
    hideWelcome();

    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${isBot ? 'bot-message' : 'user-message'} fade-in`;

    // Use marked for bot messages to support markdown
    let content = isBot ? marked.parse(message) : `<p>${escapeHtml(message)}</p>`;

    if (isBot && sources.length > 0) {
        content += '<div class="sources">';
        // Handle both simple URL strings and {title, url} objects
        const uniqueSources = sources.filter((s, index, self) => 
            s && (typeof s === 'string' ? s.startsWith('http') : (s.url && s.url.startsWith('http'))) &&
            self.findIndex(t => (typeof t === 'string' ? t : (t.url || t)) === (typeof s === 'string' ? s : (s.url || s))) === index
        );

        uniqueSources.slice(0, 3).forEach(src => {
            const url = typeof src === 'string' ? src : src.url;
            const label = typeof src === 'string' ? extractLabel(src) : (src.title || extractLabel(url));
            content += `<a href="${url}" target="_blank" rel="noopener" class="source-link">🔗 ${label}</a>`;
        });
        content += '</div>';
    }

    msgDiv.innerHTML = content;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function extractLabel(url) {
    try {
        const path = new URL(url).pathname;
        const parts = path.split('/').filter(p => p);
        if (parts.length > 0) {
            const last = parts[parts.length - 1];
            return last.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
        }
    } catch {}
    return 'Learn more';
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

async function handleSendMessage(text, retryCount = 0) {
    const msg = text || userInput.value.trim();
    if (!msg) return;

    // Show user message (only on first attempt)
    if (retryCount === 0) {
        appendMessage(msg, false);
        userInput.value = '';
        userInput.focus();
        showLoading();
    }

    const maxRetries = 2;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 seconds timeout

        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        removeLoading();

        if (data.response) {
            // Check if the response contains a 429 quota error
            if (data.response.includes('429') && retryCount < maxRetries) {
                console.log(`Quota limit hit. Retrying in 3 seconds (attempt ${retryCount + 1}/${maxRetries})...`);
                await new Promise(r => setTimeout(r, 3000));
                return handleSendMessage(msg, retryCount + 1);
            }
            appendMessage(data.response, true, data.sources || []);
        } else {
            appendMessage("I couldn't retrieve information for that query. Please try rephrasing.", true);
        }
    } catch (error) {
        console.error('Error:', error);
        removeLoading();
        
        if (error.name === 'AbortError') {
            if (retryCount < maxRetries) {
                console.log(`Timeout. Retrying (attempt ${retryCount + 1}/${maxRetries})...`);
                await new Promise(r => setTimeout(r, 2000));
                return handleSendMessage(msg, retryCount + 1);
            }
            appendMessage("⏱️ The request is taking longer than expected. This usually happens when:\n\n• The Gemini API quota is temporarily exhausted (try again in 1-2 minutes)\n• The server is processing a large context\n\nPlease **refresh and try again** in a moment. We're working to optimize this!", true);
        } else if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
            appendMessage("⚠️ **Connection Failed** — Could not reach the backend server.\n\nMake sure:\n• The backend is running on port 8000\n• Your browser can access localhost:8000\n\nTry refreshing the page or restarting the server.", true);
        } else {
            appendMessage("❌ An unexpected error occurred. Please try again or refresh the page.", true);
        }
    }
}

// --- Event Listeners ---
sendBtn.addEventListener('click', () => handleSendMessage());
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleSendMessage();
});

// Reliable Global Event Delegation for main buttons
document.addEventListener('click', (e) => {
    // Chat Widget Toggle
    const toggleBtn = e.target.closest('#chat-toggle-btn');
    if (toggleBtn) {
        e.preventDefault();
        e.stopPropagation();

        const appWrap = document.getElementById('app-wrapper');
        const input = document.getElementById('user-input');

        if (appWrap) {
            const isCurrentlyMinimized = appWrap.classList.contains('minimized');

            if (isCurrentlyMinimized) {
                // OPEN: remove minimized class (keep wrapper visible for toggle button)
                appWrap.classList.remove('minimized');
                void appWrap.offsetHeight;

                if (input) {
                    setTimeout(() => input.focus(), 50);
                }
            } else {
                // CLOSE: add minimized class (chat panel hidden but toggle remains)
                appWrap.classList.add('minimized');
                void appWrap.offsetHeight;

                if (window.parent && window.parent !== window) {
                    window.parent.postMessage('chat-minimized', '*');
                }
            }
        }
        return;
    }

    // Minimize window
    const minBtn = e.target.closest('#minimize-btn');
    if (minBtn) {
        const appWrap = document.getElementById('app-wrapper');
        if (appWrap) {
            // Add animation before minimizing
            minBtn.style.transform = 'scale(0.95)';
            minBtn.style.opacity = '0.7';
            setTimeout(() => {
                minBtn.style.transform = 'scale(1)';
                minBtn.style.opacity = '1';
                appWrap.classList.add('minimized');

                // If embedded in an iframe, notify parent to hide the iframe container
                if (window.parent && window.parent !== window) {
                    window.parent.postMessage('chat-minimized', '*');
                }
            }, 150);
        }
        return;
    }

    // Clear chat
    const clearBtn = e.target.closest('#clear-chat-btn');
    if (clearBtn) {
        const container = document.getElementById('chat-container');
        if (container) {
            // Add visual feedback
            clearBtn.style.transform = 'rotate(20deg) scale(0.9)';
            clearBtn.style.opacity = '0.6';
            
            setTimeout(() => {
                chatStarted = false;
                
                // Fade out existing content
                const messages = container.querySelectorAll('.message, .welcome-section, .suggestion-chips');
                messages.forEach(msg => {
                    msg.style.opacity = '0';
                    msg.style.transform = 'translateY(10px)';
                    msg.style.transition = 'all 0.2s ease';
                });
                
                setTimeout(() => {
                    container.innerHTML = `
                        <div class="welcome-section fade-in">
                            <div class="welcome-icon">🎓</div>
                            <h2 class="welcome-title">Welcome to SMVITM</h2>
                            <p class="welcome-desc">I'm your AI assistant for all things SMVITM. Ask me anything about admissions, departments, placements, or campus life!</p>
                        </div>
                        <div class="suggestion-chips" id="suggestion-chips">
                            <button class="chip" data-query="What courses does SMVITM offer?">📚 Courses Offered</button>
                            <button class="chip" data-query="How to get admission in SMVITM?">🎯 Admissions</button>
                            <button class="chip" data-query="Tell me about placements at SMVITM">💼 Placements</button>
                            <button class="chip" data-query="What PG programs are available?">🎓 PG Programs</button>
                            <button class="chip" data-query="Tell me about the MBA department">📊 MBA</button>
                            <button class="chip" data-query="What are the hostel facilities?">🏠 Hostel</button>
                        </div>
                    `;
                    // Remove lingering loading indicators if any
                    const loadEl = document.getElementById('loading');
                    if (loadEl) loadEl.remove();
                    
                    // Reset button style
                    clearBtn.style.transform = 'rotate(0deg) scale(1)';
                    clearBtn.style.opacity = '1';
                }, 150);
            }, 50);
        }
        return;
    }

    // Suggestion chips
    const chip = e.target.closest('.chip');
    if (chip && e.target.closest('#chat-container')) {
        const query = chip.getAttribute('data-query');
        if (query) handleSendMessage(query);
        return;
    }
});

// ===== VOICE MODE =====
function setVoiceState(state, statusText, subText) {
    voiceOrb.className = state;
    voiceStatus.innerText = statusText;
    voiceSubtext.innerText = subText;
}

function cleanupAudio() {
    if (audioContext) {
        audioContext.close().catch(() => {});
        audioContext = null;
    }
    if (animationId) cancelAnimationFrame(animationId);
    voiceOrb.style.transform = '';
    voiceOrb.style.boxShadow = '';
}

function stopListeningAndProcess() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    setVoiceState('thinking', 'Processing...', 'Thinking...');
    // Play random filler audio
    const rnd = Math.floor(Math.random() * fillerAudios.length);
    currentFillerAudio = fillerAudios[rnd];
    currentFillerAudio.currentTime = 0;
    currentFillerAudio.play().catch(e => console.log('Filler play error', e));
    cleanupAudio();
}

function visualize() {
    if (!analyser || !voiceOrb.classList.contains('listening')) return;

    const array = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(array);
    let values = 0;
    for (let i = 0; i < array.length; i++) {
        values += array[i];
    }
    const average = values / array.length;

    // Animate orb based on audio volume
    const scale = 1.1 + (average / 120);
    voiceOrb.style.transform = `scale(${scale})`;
    voiceOrb.style.boxShadow = `0 0 ${25 + average}px rgba(231, 76, 60, ${0.4 + (average / 300)})`;

    // Silence detection
    if (average > SILENCE_THRESHOLD) {
        hasSpoken = true;
        lastSpokeTime = Date.now();
    } else if (hasSpoken && (Date.now() - lastSpokeTime > SILENCE_DURATION)) {
        stopListeningAndProcess();
        return;
    }

    animationId = requestAnimationFrame(visualize);
}

// Voice overlay open
micBtn.addEventListener('click', () => {
    voiceOverlay.classList.remove('hidden');
    setVoiceState('idle', 'Voice Mode', 'Tap the orb to start speaking.');
});

// Voice overlay close
closeVoiceBtn.addEventListener('click', () => {
    voiceOverlay.classList.add('hidden');
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if (currentFillerAudio) {
        currentFillerAudio.pause();
        currentFillerAudio.currentTime = 0;
        currentFillerAudio = null;
    }
    window.speechSynthesis.cancel();
    cleanupAudio();
});

// Orb click handler
voiceOrb.addEventListener('click', async () => {
    const state = voiceOrb.className;
    
    if (state === 'idle' || state === 'speaking' || state === 'error') {
        // Start recording
        if (currentAudio) { currentAudio.pause(); currentAudio = null; }
        window.speechSynthesis.cancel();
        cleanupAudio();

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            // Audio context for visualization
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            microphone = audioContext.createMediaStreamSource(stream);
            analyser.smoothingTimeConstant = 0.5;
            analyser.fftSize = 512;
            microphone.connect(analyser);

            mediaRecorder.addEventListener("dataavailable", event => {
                audioChunks.push(event.data);
            });

            mediaRecorder.addEventListener("stop", async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                sendVoiceMessage(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            });

            mediaRecorder.start();
            setVoiceState('listening', 'Listening...', 'Speak now! (Auto-stops when you pause)');

            hasSpoken = false;
            visualize();

        } catch (err) {
            console.error("Mic error:", err);
            setVoiceState('error', 'Mic Error', 'Microphone access was denied. Please allow mic permissions.');
        }
    }
    else if (state === 'listening') {
        // Manual stop
        stopListeningAndProcess();
    }
});

function speakText(text) {
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);

    const trySpeak = () => {
        const voices = window.speechSynthesis.getVoices();
        const voice =
            voices.find(v => v.name.includes('Neerja Online (Natural)')) ||
            voices.find(v => v.name.includes('Neerja') && v.name.includes('Natural')) ||
            voices.find(v => v.name.includes('Neerja')) ||
            voices.find(v => v.lang === 'en-IN' && v.name.includes('Natural')) ||
            voices.find(v => v.lang === 'en-IN' && v.name.includes('Online')) ||
            voices.find(v => v.lang === 'en-IN') ||
            voices.find(v => v.lang.startsWith('en') && v.name.includes('Natural')) ||
            voices.find(v => v.lang.startsWith('en'));
        if (voice) utterance.voice = voice;
        utterance.rate = 0.92;
        utterance.pitch = 1.0;
        utterance.lang = 'en-IN';
        utterance.onend = () => {
            if (!voiceOverlay.classList.contains('hidden')) {
                setVoiceState('idle', 'Voice Mode', 'Tap the orb to speak again.');
            }
        };
        window.speechSynthesis.speak(utterance);
    };

    if (window.speechSynthesis.getVoices().length > 0) {
        trySpeak();
    } else {
        window.speechSynthesis.onvoiceschanged = trySpeak;
    }
}

async function sendVoiceMessage(audioBlob) {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'record.webm');

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000);

        const response = await fetch(VOICE_API_URL, {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Push interactions to text chat for history
        if (data.user_query) appendMessage(data.user_query, false);
        if (data.response) appendMessage(data.response, true, data.sources || []);

        // Stop filler
        if (currentFillerAudio) {
            currentFillerAudio.pause();
            currentFillerAudio.currentTime = 0;
            currentFillerAudio = null;
        }

        if (voiceOverlay.classList.contains('hidden')) return;

        if (data.response) {
            if (data.audio_url) {
                setVoiceState('speaking', 'Speaking...', data.response.substring(0, 120) + '...');
                currentAudio = new Audio(data.audio_url + '?t=' + Date.now());
                currentAudio.play().catch(e => {
                    console.log('Audio play error, falling back to TTS', e);
                    speakText(data.response);
                });
                currentAudio.onended = () => {
                    if (!voiceOverlay.classList.contains('hidden')) {
                        setVoiceState('idle', 'Voice Mode', 'Tap the orb to speak again.');
                    }
                };
            } else {
                setVoiceState('speaking', 'Speaking...', data.response.substring(0, 120) + '...');
                speakText(data.response);
            }
        } else {
            setVoiceState('idle', 'Voice Mode', 'Tap the orb to speak again.');
        }
    } catch (error) {
        console.error('Voice Error:', error);
        if (currentFillerAudio) {
            currentFillerAudio.pause();
            currentFillerAudio.currentTime = 0;
            currentFillerAudio = null;
        }
        if (!voiceOverlay.classList.contains('hidden')) {
            if (error.name === 'AbortError') {
                setVoiceState('error', 'Timeout', 'The request took too long. Please try again.');
            } else {
                setVoiceState('error', 'Server Busy', 'Could not reach the server. Please wait and try again.');
            }
        }
    }
}
