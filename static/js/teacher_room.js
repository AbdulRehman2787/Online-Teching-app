/**
 * Teacher Live Teaching Studio Client Logic
 * Handles WebRTC (LiveKit), PDF.js Synchronizer, Whiteboard Annotations, Roster and Chat
 */

let ws = null;
let currentBookId = null;
let currentPdfDoc = null;
let currentPageNum = 1;
let totalPages = 1;
let currentScale = 1.0;
let isDrawing = false;
let currentTool = 'pen';
let currentColor = '#ef4444';
let currentLineWidth = 3;
let currentStrokePoints = [];

// Local Media & LiveKit
let localStream = null;
let livekitRoom = null;
let activeStudents = new Map(); // sessionId -> { name, micAllowed, element }

// UI Elements
const pdfCanvas = document.getElementById('pdfCanvas');
const annotCanvas = document.getElementById('annotationCanvas');
const pdfCtx = pdfCanvas.getContext('2d');
const annotCtx = annotCanvas.getContext('2d');
const canvasWrapper = document.getElementById('canvasWrapper');
const noBookPlaceholder = document.getElementById('noBookPlaceholder');

// Initialize on DOM load
window.addEventListener('DOMContentLoaded', async () => {
    startSessionTimer();
    await initLocalMedia();
    initWebSocket();
    await connectLiveKit();
    setupDrawingEvents();
    setupChat();
});

// ==================== Session Timer ====================
function startSessionTimer() {
    const startTime = Date.now();
    const timerElem = document.getElementById('sessionTimer');
    setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const hrs = String(Math.floor(elapsed / 3600)).padStart(2, '0');
        const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
        const secs = String(elapsed % 60).padStart(2, '0');
        timerElem.textContent = `${hrs}:${mins}:${secs}`;
    }, 1000);
}

// ==================== Local Media & WebRTC ====================
async function initLocalMedia() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        const videoElem = document.getElementById('teacherLocalVideo');
        videoElem.srcObject = localStream;
    } catch (err) {
        console.warn('Could not access camera/mic:', err);
    }
}

function toggleTeacherCam() {
    if (!localStream) return;
    const track = localStream.getVideoTracks()[0];
    if (track) {
        track.enabled = !track.enabled;
        const btn = document.getElementById('teacherCamBtn');
        btn.innerHTML = track.enabled ? '<i class="fa-solid fa-video"></i>' : '<i class="fa-solid fa-video-slash text-red-400"></i>';
    }
}

function toggleTeacherMic() {
    if (!localStream) return;
    const track = localStream.getAudioTracks()[0];
    if (track) {
        track.enabled = !track.enabled;
        const btn = document.getElementById('teacherMicBtn');
        btn.innerHTML = track.enabled ? '<i class="fa-solid fa-microphone"></i>' : '<i class="fa-solid fa-microphone-slash text-red-400"></i>';
    }
}

async function connectLiveKit() {
    try {
        const res = await fetch('/api/teacher/livekit-token');
        if (!res.ok) return;
        const data = await res.json();

        if (window.LivekitClient && data.token) {
            livekitRoom = new LivekitClient.Room({
                adaptiveStream: true,
                dynacast: true,
            });

            // Handle student track publications
            livekitRoom.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                if (track.kind === LivekitClient.Track.Kind.Video) {
                    attachStudentVideoTrack(participant.identity, participant.name, track);
                } else if (track.kind === LivekitClient.Track.Kind.Audio) {
                    const audioElem = track.attach();
                    audioElem.id = `audio_${participant.identity}`;
                    document.body.appendChild(audioElem);
                }
            });

            livekitRoom.on(LivekitClient.RoomEvent.ParticipantDisconnected, (participant) => {
                removeStudentVideoTile(participant.identity);
            });

            await livekitRoom.connect(data.livekit_url, data.token);
            console.log('Connected to LiveKit Room:', data.room_name);

            // Publish local tracks
            if (localStream) {
                for (const track of localStream.getTracks()) {
                    await livekitRoom.localParticipant.publishTrack(track);
                }
            }
        }
    } catch (err) {
        console.warn('LiveKit connection note:', err.message);
    }
}

function attachStudentVideoTrack(identity, name, track) {
    let tile = document.getElementById(`tile_${identity}`);
    if (!tile) {
        tile = createStudentTile(identity, name);
    }
    const videoElem = tile.querySelector('video');
    track.attach(videoElem);
    document.getElementById('emptyStudentsMsg').classList.add('hidden');
}

function createStudentTile(identity, name) {
    const grid = document.getElementById('studentVideoGrid');
    const tile = document.createElement('div');
    tile.id = `tile_${identity}`;
    tile.className = 'video-tile relative';
    tile.innerHTML = `
        <video autoplay playsinline class="w-full h-full object-cover"></video>
        <div class="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded bg-slate-900/80 text-[10px] font-bold text-white truncate max-w-[90px]">
            ${name}
        </div>
        <div class="absolute top-1.5 right-1.5 flex items-center gap-1">
            <button onclick="kickStudentByIdentity('${identity}')" class="p-1 rounded bg-red-600/80 hover:bg-red-600 text-white text-[9px]" title="Remove Student">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>
    `;
    grid.appendChild(tile);
    return tile;
}

function removeStudentVideoTile(identity) {
    const tile = document.getElementById(`tile_${identity}`);
    if (tile) tile.remove();
    const grid = document.getElementById('studentVideoGrid');
    if (grid.children.length === 0) {
        document.getElementById('emptyStudentsMsg').classList.remove('hidden');
    }
}

// ==================== WebSocket Realtime Handshake ====================
function initWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const teacherSessionId = 'teacher_' + Math.random().toString(36).substring(2, 9);
    const wsUrl = `${proto}//${window.location.host}/ws/classroom/${teacherSessionId}?role=teacher&name=Teacher`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('Teacher WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'roster_update') {
            updateRoster(data.students, data.student_count, data.max_students);
        } else if (data.type === 'chat_message') {
            appendChatMessage(data.sender_name, data.sender_role, data.message, data.time);
        } else if (data.type === 'class_state') {
            if (data.book_id) {
                document.getElementById('bookSelect').value = data.book_id;
                currentBookId = data.book_id;
                loadPdfBook(data.book_id, data.page);
            }
        }
    };

    ws.onclose = () => {
        console.log('WebSocket closed. Reconnecting in 3s...');
        setTimeout(initWebSocket, 3000);
    };
}

function updateRoster(students, count, max) {
    document.getElementById('studentCountBadge').textContent = count;
    document.getElementById('capacityIndicator').textContent = `${count} / ${max} Max`;

    if (count > 0) {
        document.getElementById('emptyStudentsMsg').classList.add('hidden');
    } else {
        document.getElementById('emptyStudentsMsg').classList.remove('hidden');
    }

    students.forEach(s => {
        activeStudents.set(s.session_id, s);
        if (!document.getElementById(`tile_${s.session_id}`)) {
            createStudentTile(s.session_id, s.name);
        }
    });
}

// ==================== PDF.js Synchronizer ====================
async function switchBook() {
    const select = document.getElementById('bookSelect');
    const bookId = select.value;
    if (!bookId) {
        currentBookId = null;
        canvasWrapper.classList.add('hidden');
        noBookPlaceholder.classList.remove('hidden');
        return;
    }
    currentBookId = bookId;
    currentPageNum = 1;
    await loadPdfBook(bookId, 1);
    broadcastPdfSync();
}

async function loadPdfBook(bookId, pageToLoad = 1) {
    try {
        canvasWrapper.classList.remove('hidden');
        noBookPlaceholder.classList.add('hidden');

        const pdfUrl = `/books/file/${bookId}`;
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        currentPdfDoc = await loadingTask.promise;
        totalPages = currentPdfDoc.numPages;
        document.getElementById('pageCountSpan').textContent = totalPages;
        currentPageNum = pageToLoad;
        await renderPage(currentPageNum);
    } catch (err) {
        console.error('Error loading PDF:', err);
    }
}

async function renderPage(num) {
    if (!currentPdfDoc) return;
    const page = await currentPdfDoc.getPage(num);
    const viewport = page.getViewport({ scale: currentScale });

    pdfCanvas.width = viewport.width;
    pdfCanvas.height = viewport.height;
    annotCanvas.width = viewport.width;
    annotCanvas.height = viewport.height;

    const renderContext = {
        canvasContext: pdfCtx,
        viewport: viewport
    };

    await page.render(renderContext).promise;
    document.getElementById('pageNumInput').value = num;
    clearLocalCanvas();
}

function prevPage() {
    if (currentPageNum <= 1) return;
    currentPageNum--;
    renderPage(currentPageNum);
    broadcastPdfSync();
}

function nextPage() {
    if (currentPageNum >= totalPages) return;
    currentPageNum++;
    renderPage(currentPageNum);
    broadcastPdfSync();
}

function jumpToPage() {
    const input = document.getElementById('pageNumInput');
    let val = parseInt(input.value);
    if (val >= 1 && val <= totalPages) {
        currentPageNum = val;
        renderPage(currentPageNum);
        broadcastPdfSync();
    }
}

function broadcastPdfSync() {
    if (ws && ws.readyState === WebSocket.OPEN && currentBookId) {
        ws.send(JSON.stringify({
            type: 'pdf_sync',
            book_id: currentBookId,
            page: currentPageNum
        }));
    }
}

function zoomIn() {
    currentScale += 0.2;
    document.getElementById('zoomLevel').textContent = `${Math.round(currentScale * 100)}%`;
    renderPage(currentPageNum);
}

function zoomOut() {
    if (currentScale <= 0.6) return;
    currentScale -= 0.2;
    document.getElementById('zoomLevel').textContent = `${Math.round(currentScale * 100)}%`;
    renderPage(currentPageNum);
}

// ==================== Whiteboard Annotations ====================
function setTool(tool) {
    currentTool = tool;
    ['toolPen', 'toolHighlighter', 'toolLine'].forEach(id => {
        document.getElementById(id).className = 'p-1.5 rounded text-slate-400 hover:text-white';
    });
    if (tool === 'pen') document.getElementById('toolPen').className = 'p-1.5 rounded bg-indigo-600 text-white';
    if (tool === 'highlighter') document.getElementById('toolHighlighter').className = 'p-1.5 rounded bg-indigo-600 text-white';
    if (tool === 'line') document.getElementById('toolLine').className = 'p-1.5 rounded bg-indigo-600 text-white';
}

function setColor(color) {
    currentColor = color;
}

function setupDrawingEvents() {
    annotCanvas.addEventListener('mousedown', startDrawing);
    annotCanvas.addEventListener('mousemove', draw);
    annotCanvas.addEventListener('mouseup', stopDrawing);
    annotCanvas.addEventListener('mouseleave', stopDrawing);
}

function getCanvasCoords(e) {
    const rect = annotCanvas.getBoundingClientRect();
    const scaleX = annotCanvas.width / rect.width;
    const scaleY = annotCanvas.height / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
    };
}

function startDrawing(e) {
    isDrawing = true;
    const pos = getCanvasCoords(e);
    currentStrokePoints = [pos];
}

function draw(e) {
    if (!isDrawing) return;
    const pos = getCanvasCoords(e);
    currentStrokePoints.push(pos);

    annotCtx.beginPath();
    if (currentTool === 'highlighter') {
        annotCtx.strokeStyle = 'rgba(250, 204, 21, 0.4)';
        annotCtx.lineWidth = 14;
    } else {
        annotCtx.strokeStyle = currentColor;
        annotCtx.lineWidth = currentLineWidth;
    }
    annotCtx.lineCap = 'round';
    annotCtx.lineJoin = 'round';

    const p1 = currentStrokePoints[currentStrokePoints.length - 2];
    const p2 = currentStrokePoints[currentStrokePoints.length - 1];
    annotCtx.moveTo(p1.x, p1.y);
    annotCtx.lineTo(p2.x, p2.y);
    annotCtx.stroke();
}

function stopDrawing() {
    if (!isDrawing) return;
    isDrawing = false;
    if (currentStrokePoints.length > 1 && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'draw_stroke',
            stroke: {
                tool: currentTool,
                color: currentTool === 'highlighter' ? 'rgba(250, 204, 21, 0.4)' : currentColor,
                width: currentTool === 'highlighter' ? 14 : currentLineWidth,
                points: currentStrokePoints,
                page: currentPageNum
            }
        }));
    }
    currentStrokePoints = [];
}

function clearAnnotations() {
    clearLocalCanvas();
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'clear_canvas' }));
    }
}

function clearLocalCanvas() {
    annotCtx.clearRect(0, 0, annotCanvas.width, annotCanvas.height);
}

// ==================== Live Chat ====================
function setupChat() {
    const form = document.getElementById('chatForm');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('chatInput');
        const text = input.value.trim();
        if (text && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'chat_message',
                message: text
            }));
            input.value = '';
        }
    });
}

function appendChatMessage(name, role, msg, time) {
    const container = document.getElementById('chatMessages');
    const isMe = (role === 'teacher');
    const div = document.createElement('div');
    div.className = `p-2 rounded-xl text-xs max-w-[85%] ${isMe ? 'ml-auto bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200 border border-slate-700'}`;
    div.innerHTML = `
        <div class="flex items-center justify-between text-[10px] mb-1 font-semibold ${isMe ? 'text-indigo-200' : 'text-slate-400'}">
            <span>${name}</span>
            <span>${time}</span>
        </div>
        <p class="break-words">${msg}</p>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ==================== Student Remote Controls ====================
function kickStudentByIdentity(identity) {
    const sessionId = identity.replace('student_', '');
    if (!confirm('Remove this student from the live classroom?')) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'kick_student',
            target_session_id: sessionId
        }));
    }
    removeStudentVideoTile(identity);
}

// ==================== UI Tab and Layout Management ====================
function switchRightTab(tab) {
    const vContent = document.getElementById('tabContentVideos');
    const cContent = document.getElementById('tabContentChat');
    const vBtn = document.getElementById('tabBtnVideos');
    const cBtn = document.getElementById('tabBtnChat');

    if (tab === 'videos') {
        vContent.classList.remove('hidden');
        cContent.classList.add('hidden');
        vBtn.className = 'flex-1 py-2 text-indigo-400 border-b-2 border-indigo-500 flex items-center justify-center gap-1.5';
        cBtn.className = 'flex-1 py-2 text-slate-400 hover:text-slate-200 flex items-center justify-center gap-1.5';
    } else {
        vContent.classList.add('hidden');
        cContent.classList.remove('hidden');
        cBtn.className = 'flex-1 py-2 text-indigo-400 border-b-2 border-indigo-500 flex items-center justify-center gap-1.5';
        vBtn.className = 'flex-1 py-2 text-slate-400 hover:text-slate-200 flex items-center justify-center gap-1.5';
    }
}

function setLayout(mode) {
    const pdf = document.getElementById('pdfPanel');
    const right = document.getElementById('rightSidebar');
    ['btnLayoutSplit', 'btnLayoutPdf', 'btnLayoutVideo'].forEach(b => {
        document.getElementById(b).className = 'px-2.5 py-1 rounded-lg text-slate-400 hover:text-white';
    });

    if (mode === 'split') {
        pdf.classList.remove('hidden');
        right.classList.remove('hidden');
        right.style.width = '384px';
        document.getElementById('btnLayoutSplit').className = 'px-2.5 py-1 rounded-lg bg-indigo-600 text-white font-medium';
    } else if (mode === 'pdf') {
        pdf.classList.remove('hidden');
        right.classList.add('hidden');
        document.getElementById('btnLayoutPdf').className = 'px-2.5 py-1 rounded-lg bg-indigo-600 text-white font-medium';
    } else if (mode === 'video') {
        pdf.classList.add('hidden');
        right.classList.remove('hidden');
        right.style.width = '100%';
        document.getElementById('btnLayoutVideo').className = 'px-2.5 py-1 rounded-lg bg-indigo-600 text-white font-medium';
    }
}

function copyJoinLink() {
    const url = window.location.origin + '/join';
    navigator.clipboard.writeText(url);
    alert('Permanent student join link copied to clipboard!');
}

async function endSession() {
    if (!confirm('Are you sure you want to end the live class session for all students?')) return;
    try {
        await fetch('/api/teacher/classroom/end', { method: 'POST' });
        window.location.href = '/dashboard';
    } catch (err) {
        alert('Failed to end class');
    }
}
