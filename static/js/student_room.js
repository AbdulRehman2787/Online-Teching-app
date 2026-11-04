/**
 * Student Live Classroom Client Logic
 * Enforces Strict Privacy (Students only see Teacher),
 * PDF Live Page Synchronization & Realtime Whiteboard Annotations
 */

let ws = null;
let currentBookId = null;
let currentPdfDoc = null;
let currentPageNum = 1;
let totalPages = 1;
let currentScale = 1.0;
let studyMode = 'sync'; // 'sync' (Follow Teacher) or 'self' (Self-Study)
let isMicAllowedByTeacher = false;
let isSelfMicMuted = true;

// Media & LiveKit
let localStream = null;
let livekitRoom = null;

const studentSessionId = sessionStorage.getItem('student_session_id');
const studentName = sessionStorage.getItem('student_name') || 'Student';
const lkToken = sessionStorage.getItem('livekit_token');
const lkUrl = sessionStorage.getItem('livekit_url');

// UI Elements
const studentPdfCanvas = document.getElementById('studentPdfCanvas');
const studentAnnotCanvas = document.getElementById('studentAnnotationCanvas');
const studentPdfCtx = studentPdfCanvas.getContext('2d');
const studentAnnotCtx = studentAnnotCanvas.getContext('2d');
const studentCanvasWrapper = document.getElementById('studentCanvasWrapper');
const studentNoBookMsg = document.getElementById('studentNoBookMsg');

window.addEventListener('DOMContentLoaded', async () => {
    if (!studentSessionId) {
        alert('No active session found. Please join through the class link.');
        window.location.href = '/join';
        return;
    }

    document.getElementById('studentHeaderName').textContent = studentName;
    document.getElementById('selfPreviewName').textContent = studentName;

    await initLocalMedia();
    initWebSocket();
    await connectLiveKit();
    setupChat();
});

// ==================== Local Media & WebRTC ====================
async function initLocalMedia() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        const selfVideo = document.getElementById('studentSelfVideo');
        selfVideo.srcObject = localStream;
        
        // Mute local audio track initially until teacher grants permission
        localStream.getAudioTracks().forEach(track => track.enabled = false);
    } catch (err) {
        console.warn('Student camera/mic access note:', err);
    }
}

async function connectLiveKit() {
    if (!window.LivekitClient || !lkToken || !lkUrl) return;

    try {
        livekitRoom = new LivekitClient.Room({
            adaptiveStream: true,
            dynacast: true,
        });

        // ==================== STRICT PRIVACY ENFORCEMENT ====================
        // Students MUST ONLY see and hear the Teacher!
        livekitRoom.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
            const isTeacher = participant.identity.toLowerCase().startsWith('teacher');
            
            if (!isTeacher) {
                // Ignore other students' video/audio completely!
                console.log(`[PRIVACY] Track from non-teacher ${participant.identity} ignored.`);
                return;
            }

            if (track.kind === LivekitClient.Track.Kind.Video) {
                const videoElem = document.getElementById('teacherRemoteVideo');
                track.attach(videoElem);
                document.getElementById('teacherOfflineMsg').classList.add('hidden');
            } else if (track.kind === LivekitClient.Track.Kind.Audio) {
                const audioElem = track.attach();
                document.body.appendChild(audioElem);
            }
        });

        livekitRoom.on(LivekitClient.RoomEvent.ParticipantDisconnected, (participant) => {
            if (participant.identity.toLowerCase().startsWith('teacher')) {
                document.getElementById('teacherOfflineMsg').classList.remove('hidden');
            }
        });

        await livekitRoom.connect(lkUrl, lkToken);
        console.log('Student connected to LiveKit room.');

        // Publish student's camera/mic so Teacher can see & hear student
        if (localStream) {
            for (const track of localStream.getTracks()) {
                await livekitRoom.localParticipant.publishTrack(track);
            }
        }
    } catch (err) {
        console.warn('LiveKit connect warning:', err);
    }
}

// ==================== WebSocket Realtime Handshake ====================
function initWebSocket() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${window.location.host}/ws/classroom/${studentSessionId}?role=student&name=${encodeURIComponent(studentName)}`;

    ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        // 1. PDF Page Synchronization from Teacher
        if (data.type === 'pdf_sync') {
            if (studyMode === 'sync') {
                handleTeacherPdfSync(data.book_id, data.page);
            }
        }

        // 2. Teacher Drawing Stroke
        else if (data.type === 'draw_stroke') {
            if (studyMode === 'sync') {
                renderRemoteStroke(data.stroke);
            }
        }

        // 3. Clear Whiteboard Annotations
        else if (data.type === 'clear_canvas') {
            clearStudentCanvas();
        }

        // 4. Initial Class State upon joining
        else if (data.type === 'class_state') {
            if (data.book_id) {
                handleTeacherPdfSync(data.book_id, data.page);
                if (data.annotations && data.annotations.length > 0) {
                    data.annotations.forEach(stroke => renderRemoteStroke(stroke));
                }
            }
        }

        // 5. Microphone Permission from Teacher
        else if (data.type === 'mic_permission_changed') {
            handleMicPermissionChange(data.mic_allowed);
        }

        // 6. Chat Messages
        else if (data.type === 'chat_message') {
            appendStudentChatMessage(data.sender_name, data.sender_role, data.message, data.time);
        }

        // 7. Security: Teacher Changed Password
        else if (data.type === 'password_changed') {
            alert('Class password was changed by the teacher. Please re-enter with the new password.');
            sessionStorage.clear();
            window.location.href = '/join';
        }

        // 8. Security: Kicked by Teacher
        else if (data.type === 'kicked') {
            alert('You have been removed from the classroom by the teacher.');
            sessionStorage.clear();
            window.location.href = '/join';
        }

        // 9. Class Ended
        else if (data.type === 'class_ended') {
            alert('Teacher has ended the class session.');
            sessionStorage.clear();
            window.location.href = '/join';
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected.');
    };
}

// ==================== PDF.js Synchronizer & Viewer ====================
async function handleTeacherPdfSync(bookId, pageNum) {
    if (!bookId) {
        studentCanvasWrapper.classList.add('hidden');
        studentNoBookMsg.classList.remove('hidden');
        return;
    }

    if (currentBookId !== bookId) {
        currentBookId = bookId;
        await loadStudentPdfBook(bookId, pageNum);
    } else if (currentPageNum !== pageNum) {
        currentPageNum = pageNum;
        await renderStudentPage(pageNum);
    }
}

async function loadStudentPdfBook(bookId, pageToLoad = 1) {
    try {
        studentCanvasWrapper.classList.remove('hidden');
        studentNoBookMsg.classList.add('hidden');

        const pdfUrl = `/books/file/${bookId}`;
        const loadingTask = pdfjsLib.getDocument(pdfUrl);
        currentPdfDoc = await loadingTask.promise;
        totalPages = currentPdfDoc.numPages;
        document.getElementById('studentPageCount').textContent = totalPages;
        document.getElementById('bookTitleDisplay').textContent = `Book #${bookId} (${totalPages} pages)`;
        currentPageNum = pageToLoad;
        await renderStudentPage(currentPageNum);
    } catch (err) {
        console.error('Error loading PDF on student side:', err);
    }
}

async function renderStudentPage(num) {
    if (!currentPdfDoc) return;
    const page = await currentPdfDoc.getPage(num);
    const viewport = page.getViewport({ scale: currentScale });

    studentPdfCanvas.width = viewport.width;
    studentPdfCanvas.height = viewport.height;
    studentAnnotCanvas.width = viewport.width;
    studentAnnotCanvas.height = viewport.height;

    const renderContext = {
        canvasContext: studentPdfCtx,
        viewport: viewport
    };

    await page.render(renderContext).promise;
    document.getElementById('studentPageNum').textContent = num;
    clearStudentCanvas();
}

function prevStudentPage() {
    if (currentPageNum <= 1) return;
    currentPageNum--;
    renderStudentPage(currentPageNum);
}

function nextStudentPage() {
    if (currentPageNum >= totalPages) return;
    currentPageNum++;
    renderStudentPage(currentPageNum);
}

function setStudyMode(mode) {
    studyMode = mode;
    const syncBtn = document.getElementById('modeSyncBtn');
    const selfBtn = document.getElementById('modeSelfBtn');
    const nav = document.getElementById('selfStudyNav');
    const syncIndicator = document.getElementById('syncIndicator');

    if (mode === 'sync') {
        syncBtn.className = 'px-2 py-0.5 rounded-lg bg-indigo-600 text-white font-semibold text-[11px]';
        selfBtn.className = 'px-2 py-0.5 rounded-lg text-slate-400 hover:text-white font-medium text-[11px] ml-1';
        nav.classList.add('hidden');
        nav.classList.remove('flex');
        syncIndicator.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i><span>Live Sync Active</span>';
    } else {
        selfBtn.className = 'px-2 py-0.5 rounded-lg bg-indigo-600 text-white font-semibold text-[11px] ml-1';
        syncBtn.className = 'px-2 py-0.5 rounded-lg text-slate-400 hover:text-white font-medium text-[11px]';
        nav.classList.remove('hidden');
        nav.classList.add('flex');
        syncIndicator.innerHTML = '<i class="fa-solid fa-book-open-reader text-amber-400"></i><span>Self-Study Mode</span>';
    }
}

// ==================== Annotation Rendering ====================
function renderRemoteStroke(stroke) {
    if (!stroke || !stroke.points || stroke.points.length < 2) return;

    studentAnnotCtx.beginPath();
    studentAnnotCtx.strokeStyle = stroke.color || '#ef4444';
    studentAnnotCtx.lineWidth = stroke.width || 3;
    studentAnnotCtx.lineCap = 'round';
    studentAnnotCtx.lineJoin = 'round';

    studentAnnotCtx.moveTo(stroke.points[0].x, stroke.points[0].y);
    for (let i = 1; i < stroke.points.length; i++) {
        studentAnnotCtx.lineTo(stroke.points[i].x, stroke.points[i].y);
    }
    studentAnnotCtx.stroke();
}

function clearStudentCanvas() {
    studentAnnotCtx.clearRect(0, 0, studentAnnotCanvas.width, studentAnnotCanvas.height);
}

// ==================== Microphone Controls ====================
function handleMicPermissionChange(allowed) {
    isMicAllowedByTeacher = allowed;
    const btn = document.getElementById('studentMicBtn');
    const statusText = document.getElementById('micStatusText');
    const btnLabel = document.getElementById('studentMicBtnLabel');

    if (allowed) {
        btn.disabled = false;
        btn.className = 'px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer';
        statusText.textContent = 'Mic Permission Granted';
        statusText.className = 'text-emerald-400 text-[10px] font-semibold';
        btnLabel.textContent = isSelfMicMuted ? 'Unmute' : 'Mute';
    } else {
        // Force muted
        isSelfMicMuted = true;
        if (localStream) {
            localStream.getAudioTracks().forEach(t => t.enabled = false);
        }
        btn.disabled = true;
        btn.className = 'px-3 py-1.5 rounded-lg bg-slate-700 text-slate-400 text-xs font-semibold cursor-not-allowed flex items-center gap-1.5';
        statusText.textContent = 'Mic Muted by Teacher';
        statusText.className = 'text-slate-400 text-[10px]';
        btnLabel.textContent = 'Muted';
        btn.querySelector('i').className = 'fa-solid fa-microphone-slash';
    }
}

function toggleStudentSelfMic() {
    if (!isMicAllowedByTeacher || !localStream) return;
    const audioTrack = localStream.getAudioTracks()[0];
    if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        isSelfMicMuted = !audioTrack.enabled;
        const btn = document.getElementById('studentMicBtn');
        const btnLabel = document.getElementById('studentMicBtnLabel');
        if (audioTrack.enabled) {
            btnLabel.textContent = 'Mute';
            btn.querySelector('i').className = 'fa-solid fa-microphone';
            btn.className = 'px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer';
        } else {
            btnLabel.textContent = 'Unmute';
            btn.querySelector('i').className = 'fa-solid fa-microphone-slash';
            btn.className = 'px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer';
        }
    }
}

// ==================== Live Chat ====================
function setupChat() {
    const form = document.getElementById('studentChatForm');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('studentChatInput');
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

function appendStudentChatMessage(name, role, msg, time) {
    const container = document.getElementById('studentChatMessages');
    const isTeacher = (role === 'teacher');
    const isMe = (name === studentName);
    const div = document.createElement('div');
    
    div.className = `p-2 rounded-xl text-xs max-w-[85%] ${
        isMe 
        ? 'ml-auto bg-indigo-600 text-white' 
        : isTeacher 
        ? 'bg-slate-800 text-slate-100 border border-indigo-500/50' 
        : 'bg-slate-850 bg-slate-800 text-slate-200 border border-slate-700'
    }`;

    div.innerHTML = `
        <div class="flex items-center justify-between text-[10px] mb-1 font-semibold ${isTeacher ? 'text-indigo-300' : 'text-slate-400'}">
            <span>${name} ${isTeacher ? '(Teacher)' : ''}</span>
            <span>${time}</span>
        </div>
        <p class="break-words">${msg}</p>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function leaveClass() {
    if (confirm('Leave the classroom?')) {
        sessionStorage.clear();
        window.location.href = '/join';
    }
}
