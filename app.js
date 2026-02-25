/* ================================
   GI COPILOT - CLIENT APPLICATION
   WebSocket Voice Architecture
================================ */
/* ================================
   GI COPILOT - CLIENT APPLICATION
================================ */

let currentTab = 'live';
let selectedFile = null;
let currentSessionId = null;

// Backend video conversion
async function convertVideoOnServer(file, progressCallback) {
  try {
    progressCallback?.('Uploading video for conversion...');
    
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/convert/to-mp4', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Conversion failed');
    }
    
    progressCallback?.('Converting video...');
    
    // Get the converted video as blob
    const blob = await response.blob();
    
    // Create a new File object
    const convertedFile = new File(
      [blob], 
      file.name.replace(/\.[^.]+$/, '.mp4'),
      { type: 'video/mp4' }
    );
    
    progressCallback?.('Conversion complete!');
    
    return convertedFile;
  } catch (error) {
    console.error('Server conversion error:', error);
    throw error;
  }
}

// Check if video needs conversion
async function checkVideoCodec(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/convert/check-codec', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) return { needs_conversion: true };
    
    const result = await response.json();
    console.log('Codec check:', result);
    
    return result;
  } catch (error) {
    console.error('Codec check error:', error);
    return { needs_conversion: true };
  }
}

// Tab Switching
function switchTab(tabName) {
  currentTab = tabName;
  
  // Update tab buttons
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.classList.remove('active');
    if (tab.textContent.toLowerCase().includes(tabName)) {
      tab.classList.add('active');
    }
  });
  
  // Update content
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
  });
  document.getElementById(`${tabName}-tab`).classList.add('active');
  
  // Load data if needed
  if (tabName === 'sessions') {
    loadSessions();
  }
}

/* ================================
   LIVE SESSION - REAL-TIME VOICE
================================ */

let videoReady = false;
let peerConnection;
let dataChannel;
let lastClarify = 0;

// Get elements (will be set when page loads)
let video, statusText, micCircle;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  video = document.getElementById("endoVideo");
  statusText = document.getElementById("statusText");
  micCircle = document.getElementById("micCircle");
  
  // Add metadata listener
  if (video) {
    video.addEventListener("loadedmetadata", () => {
      console.log("✅ Video metadata loaded");
      videoReady = true;
    });
  }
  
  // DON'T start voice session until video is ready
  // Voice session will start when video loads (in loadLiveVideo)
});

// Load local video file for live demo
async function loadLiveVideo(event) {
  const file = event.target.files[0];
  if (!file) return;
  
  // Validate video file
  if (!file.type.startsWith('video/')) {
    alert('Please select a valid video file');
    return;
  }
  
  console.log("Loading video file:", file.name, "Type:", file.type, "Size:", file.size);
  
  // Get elements first
  const prompt = document.getElementById('videoLoadPrompt');
  const videoEl = document.getElementById('endoVideo');
  const statusEl = document.getElementById('statusText');
  
  // Hide the prompt (check if exists)
  if (prompt) {
    prompt.style.display = 'none';
  }
  
  // Check video element
  if (!videoEl) {
    console.error("Video element not found!");
    return;
  }
  
  try {
    let videoFile = file;
    
    // Check if video needs conversion
    if (statusEl) statusEl.innerText = "🔍 Checking video format...";
    
    const codecInfo = await checkVideoCodec(file);
    
    if (codecInfo.needs_conversion) {
      console.log("⚠️ Video needs conversion:", codecInfo.reason || codecInfo.current_codec);
      
      if (statusEl) {
        statusEl.innerText = "🔄 Converting video to browser-compatible format...";
      }
      
      // Convert using backend
      videoFile = await convertVideoOnServer(file, (message) => {
        console.log("Conversion:", message);
        if (statusEl) statusEl.innerText = "🔄 " + message;
      });
      
      console.log("✅ Video converted successfully");
      if (statusEl) statusEl.innerText = "✅ Video ready";
    } else {
      console.log("✅ Video codec compatible:", codecInfo.current_codec);
    }
    
    const videoURL = URL.createObjectURL(videoFile);
    console.log("Created video URL:", videoURL);
    
    videoEl.src = videoURL;
    videoEl.style.display = 'block';
    
    // Set supported codecs explicitly
    if (videoEl.canPlayType) {
      const mp4Support = videoEl.canPlayType('video/mp4; codecs="avc1.42E01E, mp4a.40.2"');
      console.log("MP4 H.264/AAC support:", mp4Support);
    }
    
    videoEl.load(); // Ensure video is loaded
  
  // Update video reference
  video = videoEl;
  
  // Update status
 
  if (statusEl) {
    statusEl.innerText = "📹 Video loaded. Click play to start...";
    statusText = statusEl;
  }
  
  // Play after loaded
  videoEl.addEventListener('loadeddata', () => {
    console.log("✅ Video data loaded");
    videoReady = true;
    
    // ✅ MUTE VIDEO - we only need visuals, not audio
    videoEl.muted = true;
    console.log("🔇 Video muted (voice chat needs audio channel)");
    
    // Start live session
    startLiveSession();
    
    // ✅ Start voice session NOW (after video ready)
    startVoiceSession();

    
    
    // Try to play
    videoEl.play().then(() => {
      console.log("▶️ Video playing automatically");
      if (statusText) statusText.innerText = "👂 Listening...";
     startFrameCapture();
      
    }).catch(err => {
      console.log("⏸ Autoplay prevented - click play button");
      if (statusText) statusText.innerText = "📹 Click play button to start";
    });
  }, { once: true });
  videoEl.addEventListener('ended', () => {
  console.log('🏁 Video ended');
  stopFrameCapture();
});



videoEl.addEventListener('play', () => {
  console.log('▶️ Video resumed');
  startFrameCapture();
});
  // Handle errors
  videoEl.addEventListener('error', (e) => {
    console.error("Video loading error:", e);
    console.error("Video element state:", {
      src: videoEl.src,
      error: videoEl.error,
      errorCode: videoEl.error?.code,
      errorMessage: videoEl.error?.message,
      networkState: videoEl.networkState,
      readyState: videoEl.readyState,
      currentSrc: videoEl.currentSrc
    });
    
    let errorMsg = 'Error loading video. ';
    let shouldRetry = false;
    
    if (videoEl.error) {
      switch(videoEl.error.code) {
        case 1: 
          errorMsg += 'Video loading aborted.'; 
          break;
        case 2: 
          errorMsg += 'Network error - check your connection.'; 
          break;
        case 3: 
          errorMsg += 'Video decoding failed. The video file may be corrupted.';
          shouldRetry = true;
          break;
        case 4: 
          errorMsg += 'Video codec not supported by your browser.';
          shouldRetry = true;
          break;
        default:
          errorMsg += 'Unknown error occurred.';
      }
    }
    
    
    // Try re-encoding if codec issue
    if (shouldRetry && !videoFile.wasConverted) {
      console.log("🔄 Attempting to re-encode video...");
      if (statusEl) statusEl.innerText = "🔄 Re-encoding video for compatibility...";
      
      // Mark to avoid infinite loop
      videoFile.wasConverted = true;
      
      // Try conversion even for MP4 (might have incompatible codec)
      convertVideoToMP4(videoFile, (message) => {
        console.log("Re-encoding:", message);
        if (statusEl) statusEl.innerText = "🔄 " + message;
      }).then(convertedFile => {
        // Retry with converted file
        const newURL = URL.createObjectURL(convertedFile);
        videoEl.src = newURL;
        videoEl.load();
      }).catch(err => {
        console.error("Re-encoding failed:", err);
        alert(errorMsg + '\n\nRe-encoding failed. Please try a different video file.');
        if (prompt) prompt.style.display = 'block';
        videoEl.style.display = 'none';
      });
      
      return; // Don't show alert yet
    }
    
    alert(errorMsg);
    
    // Reset UI
    if (prompt) prompt.style.display = 'block';
    videoEl.style.display = 'none';
  });
  
  } catch (error) {
    console.error("Error in loadLiveVideo:", error);
    
    let errorMsg = 'Failed to load video file';
    if (error.message && error.message.includes('converter')) {
      errorMsg = 'Video conversion failed. Please use MP4 format.';
    }
    
    alert(errorMsg + (error.message ? ': ' + error.message : ''));
    if (prompt) prompt.style.display = 'block';
    if (statusEl) statusEl.innerText = "❌ Failed to load video";
  }
}

// Video ready handler - removed duplicate

// Snapshot sending
async function sendSnapshot() {
  if (!videoReady) return;
  if (video.paused || video.ended) return;

  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;

  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0);

  canvas.toBlob(async blob => {
    const formData = new FormData();
    formData.append("file", blob, "frame.jpg");

    try {
      const response = await fetch("/api/gi/snapshot", {
        method: "POST",
        body: formData
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log("📸 Snapshot sent");
        
        // ✅ AUTO-INJECT MEDGEMMA FINDINGS
        if (data.result && window.voiceDataChannel && 
            window.voiceDataChannel.readyState === 'open') {
          window.voiceDataChannel.send(JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "message",
              role: "user",
              content: [{
                type: "input_text",
                text: `[New MedGemma Finding] ${data.result}`
              }]
            }
          }));
          console.log("💉 Injected MedGemma finding into voice context");
        }
      }
    } catch (error) {
      console.error("Error sending snapshot:", error);
    }
  }, "image/jpeg", 0.8);
}

// ===== STRICT Finding Extraction - Removes Duplicates =====

function extractStructuredFinding(text) {
  // CRITICAL: Remove empty label structures first
  // Pattern: "Finding:\nLocation:\nRisk Level (Low/Medium/High):\nSuggested Next Step:"
  const emptyStructure = /Finding:\s*\n\s*Location:\s*\n\s*Risk Level \(Low\/Medium\/High\):\s*\n\s*Suggested Next Step:\s*/gi;
  let cleaned = text.replace(emptyStructure, '');
  
  // Also remove inline empty structure
  const emptyInline = /^Finding:\s*Location:\s*Risk Level \(Low\/Medium\/High\):\s*Suggested Next Step:\s*/gi;
  cleaned = cleaned.replace(emptyInline, '');
  
  // Remove system prompts
  const promptPatterns = [
    /You are MedGemma.*?(?=Finding:|Location:|Risk Level:|$)/is,
    /Analyze this.*?(?=Finding:|Location:|Risk Level:|$)/is,
    /Return ONLY structured output.*?(?=Finding:|Location:|Risk Level:|$)/is,
    /\[System\].*?(?=Finding:|Location:|Risk Level:|$)/is,
    /Do NOT provide.*?(?=Finding:|Location:|Risk Level:|$)/is,
    /Be cautious.*?(?=Finding:|Location:|Risk Level:|$)/is,
    /<start_of_image>.*?(?=Finding:|Location:|Risk Level:|$)/is
  ];
  
  promptPatterns.forEach(pattern => {
    cleaned = cleaned.replace(pattern, '');
  });
  
  // Flexible pattern to handle both formats
  const pattern = /Finding:\s*(.*?)\s*\n\s*Location:\s*(.*?)\s*\n\s*Risk(?:\s+Level)?(?:\s*\(Low\/Medium\/High\))?:\s*(.*?)\s*\n\s*Suggested (?:Next Step|Action):\s*(.*?)(?:\n|$)/is;
  
  const match = cleaned.match(pattern);
  
  if (match) {
    const finding = match[1].trim();
    const location = match[2].trim();
    const risk = match[3].trim();
    const action = match[4].trim();
    
    // ✅ STRICT VALIDATION
    // Must have actual finding content (not empty, not whitespace)
    if (!finding || finding.length < 3) {
      console.log('⚠️ Skipping - empty finding field');
      return null;
    }
    
    // Skip if finding contains artifacts
    if (finding.toLowerCase().includes('medgemma') || 
        finding.toLowerCase().includes('analyze')) {
      console.log('⚠️ Skipping - prompt artifact in finding');
      return null;
    }
    
    return {
      finding: finding,
      location: location || 'Not specified',
      risk_level: risk || 'Unknown',
      suggested_action: action || 'Continue observation'
    };
  }
  
  console.log('⚠️ No valid structured pattern found');
  return null;
}

// Fallback cleaner (rarely used now)
function cleanFinding(text) {
  let cleaned = text
    // Remove empty structures
    .replace(/Finding:\s*\n\s*Location:\s*\n\s*Risk Level \(Low\/Medium\/High\):\s*\n\s*Suggested Next Step:\s*/gi, '')
    .replace(/^Finding:\s*Location:\s*Risk Level \(Low\/Medium\/High\):\s*Suggested Next Step:\s*/gi, '')
    
    // Remove prompts
    .replace(/You are MedGemma.*?(?=Finding:|Location:|$)/is, '')
    .replace(/Analyze this.*?(?=Finding:|Location:|$)/is, '')
    .replace(/Return ONLY.*?(?=Finding:|Location:|$)/is, '')
    .replace(/Do NOT provide.*?(?=Finding:|Location:|$)/is, '')
    
    // Remove artifacts
    .replace(/\[New MedGemma Finding\]/g, '')
    .replace(/\[System\].*$/gm, '')
    .replace(/^System:.*$/gm, '')
    .replace(/^User:.*$/gm, '')
    .trim();
  
  if (cleaned.length < 10) {
    return null;
  }
  
  return cleaned.substring(0, 300) + (cleaned.length > 300 ? '...' : '');
}

// ===== UPDATED refreshTimeline with Strict Validation =====

async function refreshTimeline() {
  try {
    const res = await fetch("/api/gi/timeline");
    
    if (!res.ok) {
      console.log("Timeline endpoint not ready yet");
      return;
    }
    
    const data = await res.json();

    const list = document.getElementById("findingsList");
    if (!list) return;
    
    list.innerHTML = "";

    const recentFindings = data.timeline.slice(-10);
    
    if (recentFindings.length === 0) {
      list.innerHTML = '<li style="opacity: 0.5; text-align: center; padding: 40px;">No findings yet...</li>';
      return;
    }

    let validCount = 0;

    recentFindings.forEach(entry => {
      // Get the finding text
      let findingText = '';
      let timestamp = 'Just now';
      
      if (typeof entry === 'object') {
        findingText = entry.finding || entry.text || String(entry);
        timestamp = entry.time || entry.timestamp || 'Just now';
      } else {
        findingText = String(entry);
      }
      
      // ✅ STRICT VALIDATION - Skip invalid entries
      // Empty structure check
      if (findingText.match(/^Finding:\s*\n\s*Location:\s*\n\s*Risk Level/)) {
        console.log('⚠️ Skipping empty structure entry');
        return;
      }
      
      // Must have "Finding:" with actual content
      if (!findingText.includes('Finding:')) {
        console.log('⚠️ Skipping - no Finding: label');
        return;
      }
      
      // Skip prompt-only entries
      if (findingText.includes('You are MedGemma') && 
          !findingText.match(/Finding:\s*\w+/)) {
        console.log('⚠️ Skipping prompt-only entry');
        return;
      }
      
      // Extract structured finding
      const structured = extractStructuredFinding(findingText);
      
      const li = document.createElement("li");
      li.className = "finding-item";
      
      if (structured) {
        // Display structured format
        li.innerHTML = `
          <div class="finding-time">${timestamp}</div>
          <div class="finding-text">
            <div style="margin-bottom: 8px;">
              <strong style="color: #4CAF50;">Finding:</strong> ${structured.finding}
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 13px; opacity: 0.9;">
              <div>
                <strong>Location:</strong> ${structured.location}
              </div>
              <div>
                <strong>Risk:</strong> 
                <span class="risk-badge risk-${structured.risk_level.toLowerCase()}">${structured.risk_level}</span>
              </div>
            </div>
            ${structured.suggested_action && structured.suggested_action !== 'Continue observation' ? `
              <div style="margin-top: 8px; padding: 8px; background: rgba(255,193,7,0.1); border-left: 2px solid #FFC107; font-size: 12px;">
                <strong>⚠️ Suggested Action:</strong> ${structured.suggested_action}
              </div>
            ` : ''}
          </div>
        `;
        validCount++;
      } else {
        // Fallback: try cleaning
        const cleanText = cleanFinding(findingText);
        
        if (cleanText) {
          li.innerHTML = `
            <div class="finding-time">${timestamp}</div>
            <div class="finding-text">${cleanText}</div>
          `;
          validCount++;
        } else {
          console.log('⚠️ No valid content after cleaning');
          return; // Skip this entry
        }
      }
      
      list.appendChild(li);
    });
    
    // If all entries were filtered out
    if (validCount === 0) {
      list.innerHTML = '<li style="opacity: 0.5; text-align: center; padding: 40px;">Waiting for analysis...</li>';
    }
    
    console.log(`📊 Timeline rendered: ${validCount} valid findings from ${recentFindings.length} total`);
    
  } catch (error) {
    console.error("Timeline refresh error:", error);
  }
}

// Call refreshTimeline every 4 seconds
setInterval(refreshTimeline, 2000);

// Add CSS for risk badges (add to your HTML <style> section)
const riskBadgeStyles = `
.risk-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 4px;
}

.risk-high {
  background: rgba(244, 67, 54, 0.2);
  color: #F44336;
}

.risk-medium {
  background: rgba(255, 193, 7, 0.2);
  color: #FFC107;
}

.risk-low {
  background: rgba(76, 175, 80, 0.2);
  color: #4CAF50;
}
`;

// Auto-inject styles if not present
if (!document.getElementById('risk-badge-styles')) {
  const styleEl = document.createElement('style');
  styleEl.id = 'risk-badge-styles';
  styleEl.textContent = riskBadgeStyles;
  document.head.appendChild(styleEl);
}

function extractCleanFinding(text) {
  // Remove everything before "Finding:" or similar markers
  const patterns = [
    /Finding:\s*(.*?)(?:\n|$)/i,
    /Location:\s*(.*?)(?:\n|$)/i,
    /Risk Level:\s*(.*?)(?:\n|$)/i,
    /Observation:\s*(.*?)(?:\n|$)/i
  ];
  
  let cleaned = text;
  
  // Try to extract structured content
  const findingMatch = text.match(/Finding:\s*([\s\S]*?)(?=Location:|Risk Level:|Suggested Action:|$)/i);
  const locationMatch = text.match(/Location:\s*([\s\S]*?)(?=Finding:|Risk Level:|Suggested Action:|$)/i);
  const riskMatch = text.match(/Risk Level:\s*([\s\S]*?)(?=Finding:|Location:|Suggested Action:|$)/i);
  
  if (findingMatch || locationMatch || riskMatch) {
    let parts = [];
    if (findingMatch) parts.push(`<strong>Finding:</strong> ${findingMatch[1].trim()}`);
    if (locationMatch) parts.push(`<strong>Location:</strong> ${locationMatch[1].trim()}`);
    if (riskMatch) parts.push(`<strong>Risk:</strong> ${riskMatch[1].trim()}`);
    
    return parts.join(' | ');
  }
  
  // Fallback: just remove common prompt artifacts
  cleaned = cleaned
    .replace(/^.*?(?:analyze|describe|identify|examine).*?:/i, '')
    .replace(/\[New MedGemma Finding\]/g, '')
    .replace(/^System:.*$/gm, '')
    .replace(/^User:.*$/gm, '')
    .trim();
  
  return cleaned.substring(0, 200) + (cleaned.length > 200 ? '...' : '');
}




let procedureEnded = false;
let inactivityTimer = null;
const INACTIVITY_THRESHOLD = 120000; // 2 minutes of no activity

function detectProcedureEnd() {
  // Reset timer on any activity
  clearTimeout(inactivityTimer);
  
  if (procedureEnded) return;
  
  inactivityTimer = setTimeout(() => {
    console.log('⏸️ Procedure inactivity detected - auto-saving...');
    autoSaveProcedure();
  }, INACTIVITY_THRESHOLD);
}

async function autoSaveProcedure() {
  if (procedureEnded) return;
  
  procedureEnded = true;
  console.log('🏁 Auto-saving procedure session...');
  
  try {
    const timestamp = new Date().toLocaleString();
    const response = await fetch('/api/gi/session/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: `Procedure Session - ${timestamp}`,
        procedure_type: 'auto_saved'
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('✅ Session auto-saved:', data.session_id);
      
      // Show notification
      if (statusText) {
        statusText.innerText = "✅ Session auto-saved";
        setTimeout(() => {
          statusText.innerText = "Ready for next procedure";
        }, 3000);
      }
      
      // Reset for next procedure
      setTimeout(() => {
        resetForNextProcedure();
      }, 5000);
    }
  } catch (error) {
    console.error('Auto-save failed:', error);
  }
}

function resetForNextProcedure() {
  console.log('🔄 Resetting for next procedure...');
  
  // Clear findings
  const list = document.getElementById("findingsList");
  if (list) {
    list.innerHTML = '<li style="opacity: 0.5; text-align: center; padding: 40px;">Ready for next procedure...</li>';
  }
  
  // Reset state
  procedureEnded = false;
  
  // Keep voice session active
  if (statusText) {
    statusText.innerText = "👂 Ready for next procedure";
  }
  
  console.log('✅ Ready for next procedure');
}
/* ================================
   LIVE SESSION MANAGEMENT
================================ */

// Start live session when video loads
async function startLiveSession() {
  try {
    const response = await fetch('/api/gi/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: `Live Session ${new Date().toLocaleString()}`
      })
    });
    
    const data = await response.json();
    console.log('🎬 Live session started:', data.session_id);
    
    // Show save button
    const saveBtn = document.getElementById('saveSessionBtn');
    if (saveBtn) saveBtn.style.display = 'block';
    
    return data.session_id;
  } catch (error) {
    console.error('Failed to start session:', error);
  }
}

// Add this AFTER startLiveSession() function (around line 750)

let frameIntervalId = null;

// Start capturing frames every 3 seconds
function startFrameCapture() {
  // Stop any existing interval
  if (frameIntervalId) {
    clearInterval(frameIntervalId);
  }
  
  console.log('📸 Starting frame capture (every 3 seconds)');
  
  // Capture first frame immediately
  sendSnapshot();
  
  // Then capture every 2 seconds
  frameIntervalId = setInterval(() => {
    if (video && !video.paused && !video.ended && videoReady) {
      sendSnapshot();
    }
  }, 2000); // Every 2 seconds
}

// Stop frame capture
function stopFrameCapture() {
  if (frameIntervalId) {
    clearInterval(frameIntervalId);
    frameIntervalId = null;
    console.log('⏹ Frame capture stopped');
  }
}

// Save live session
async function saveLiveSession() {
  try {
    const title = prompt('Enter session title:', `Live Session ${new Date().toLocaleDateString()}`);
    if (!title) return;
    
    const procedureType = prompt('Procedure type (upper_gi/colonoscopy/other):', 'other');
    
    const saveBtn = document.getElementById('saveSessionBtn');
    if (saveBtn) saveBtn.innerText = '💾 Saving...';
    
    const response = await fetch('/api/gi/session/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: title,
        procedure_type: procedureType || 'other'
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      alert('Failed to save session: ' + error.error);
      if (saveBtn) saveBtn.innerText = '💾 Save Session';
      return;
    }
    
    const data = await response.json();
    
    alert(`✅ Session saved successfully!

Title: ${data.title}
Findings: ${data.findings_count}

View in "My Sessions" tab.`);
    
    if (saveBtn) {
      saveBtn.innerText = '✅ Saved';
      setTimeout(() => {
        saveBtn.innerText = '💾 Save Session';
      }, 2000);
    }
    
    // Reload sessions tab
    loadSessions();
    
  } catch (error) {
    console.error('Save session error:', error);
    alert('Failed to save session: ' + error.message);
    
    const saveBtn = document.getElementById('saveSessionBtn');
    if (saveBtn) saveBtn.innerText = '💾 Save Session';
  }
}

/* ================================
   WEBSOCKET VOICE SESSION
   (Backend WebSocket Proxy)
================================ */


/* ================================
   WEBSOCKET VOICE SESSION
================================ */

class WebSocketVoiceSession {
  constructor() {
    this.ws = null;
    this.peerConnection = null;
    this.dataChannel = null;
    this.audioElement = null;
    this.isActive = false;
  }

  async initialize() {
    try {
      console.log('🚀 Initializing WebSocket voice session...');
      
      const micStream = await navigator.mediaDevices.getUserMedia({ 
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 }
      });
      console.log('✅ Microphone access granted');
      
      this.peerConnection = new RTCPeerConnection({ 
        iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] 
      });
      
      this.audioElement = document.createElement("audio");
      this.audioElement.autoplay = true;
      this.audioElement.volume = 1.0;
      this.audioElement.muted = false;
      document.body.appendChild(this.audioElement);
      
      this.peerConnection.ontrack = (e) => {
        console.log('🔊 Received audio track from AI');
        this.audioElement.srcObject = e.streams[0];
      };
      
      this.peerConnection.addTrack(micStream.getAudioTracks()[0], micStream);
      console.log('🎤 Added microphone track');
      
      this.dataChannel = this.peerConnection.createDataChannel("oai-events");
      window.voiceDataChannel = this.dataChannel;
      this.setupDataChannel();
      
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/api/gi/realtime`;
      
      console.log('📡 Connecting to WebSocket:', wsUrl);
      this.ws = new WebSocket(wsUrl);
      
      this.ws.onopen = async () => {
        console.log('✅ WebSocket connected to backend');
        const offer = await this.peerConnection.createOffer();
        await this.peerConnection.setLocalDescription(offer);
        this.ws.send(JSON.stringify({ type: 'webrtc_offer', sdp: offer.sdp }));
        console.log('📤 Sent WebRTC offer');
      };
      
      this.ws.onmessage = (e) => {
        try { this.handleMessage(JSON.parse(e.data)); }
        catch(err) { console.error('Parse error:', err); }
      };
      
      this.ws.onerror = (e) => console.error('❌ WebSocket error:', e);
      this.ws.onclose = () => {
        console.log('🔴 WebSocket closed');
        this.isActive = false;
      };
      
      this.isActive = true;
      
    } catch (error) {
      console.error('❌ Voice session init failed:', error);
      if (statusText) statusText.innerText = "❌ Voice setup failed";
    }
  }

  setupDataChannel() {
    this.dataChannel.onopen = () => {
      console.log('✅ Data channel open');
      if (statusText) statusText.innerText = "👂 Listening...";
      if (micCircle) micCircle.classList.remove('disabled');
    };
  }

  handleMessage(msg) {
    const t = msg.type;
    if (t !== 'response.audio.delta') console.log('📨', t);
    
    if (t === 'webrtc_answer') {
      this.peerConnection.setRemoteDescription({ type: 'answer', sdp: msg.sdp });
      console.log('✅ WebRTC connection established');
    }
    else if (t === 'input_audio_buffer.speech_started') {
      if (micCircle) micCircle.classList.add('speaking');
      if (statusText) statusText.innerText = "🎤 You're speaking...";
    }
    else if (t === 'input_audio_buffer.speech_stopped') {
      if (micCircle) micCircle.classList.remove('speaking');
      if (statusText) statusText.innerText = "⏳ Processing...";
    }
    else if (t === 'response.audio.delta') {
      if (micCircle) micCircle.classList.add('speaking');
      if (statusText) statusText.innerText = "🗣 AI Speaking...";
    }
    else if (t === 'response.audio.done') {
      if (micCircle) micCircle.classList.remove('speaking');
      if (statusText) statusText.innerText = "👂 Listening...";
    }
    else if (t === 'conversation.item.created') {
      if (msg.item?.content?.[0]?.text?.includes('[New MedGemma Finding]')) {
        console.log('💉 MedGemma finding injected');
      }
    }
    else if (t === 'error') {
      console.error('❌ OpenAI error:', msg.error);
      if (statusText) statusText.innerText = "❌ Error";
    }
  }

  sendMessage(m) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(m));
    }
  }

  close() {
    if (this.ws) this.ws.close();
    if (this.dataChannel) this.dataChannel.close();
    if (this.peerConnection) this.peerConnection.close();
    if (this.audioElement) {
      this.audioElement.srcObject = null;
      this.audioElement.remove();
    }
    this.isActive = false;
  }
}

let voiceSession = null;



// Global voice session instance

// OpenAI Realtime Voice Session (WebSocket-based)
async function startVoiceSession() {
  statusText.innerText = "🎧 Connecting to Voice AI...";

  try {
    // Get ephemeral token
    const tokenRes = await fetch("/api/gi/realtime/token", { method: "POST" });
    const tokenData = await tokenRes.json();
    const token = tokenData.client_secret;

    // Get microphone access
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    peerConnection = new RTCPeerConnection();
    
    // ✅ CRITICAL: Add audio transceiver for RECEIVING audio from OpenAI
    peerConnection.addTransceiver('audio', { direction: 'recvonly' });
    
    // Add our microphone for SENDING audio to OpenAI
    peerConnection.addTrack(stream.getAudioTracks()[0], stream);
    
    console.log("🔗 Peer connection configured for bidirectional audio");

    // Audio playback - MUST be in DOM to play
    const audioEl = document.createElement("audio");
    audioEl.autoplay = true;
    audioEl.volume = 1.0;      // ← Max volume for AI
    audioEl.muted = false;     // ← Ensure not muted
    document.body.appendChild(audioEl);  // ← CRITICAL FIX
    updateStatusIndicator(true);
    // ✅ CRITICAL: Resume audio context on user interaction (Chrome autoplay policy)
    let audioUnlocked = false;
    const unlockAudio = () => {
      if (audioUnlocked) return;
      
      // Create a silent audio context and resume it
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioCtx.resume().then(() => {
        console.log("🔓 Audio unlocked by user interaction");
        audioUnlocked = true;
        
        // Also try to play the audio element
        if (audioEl.srcObject) {
          audioEl.play()
            .then(() => console.log("✅ Audio playing after unlock"))
            .catch(e => console.log("⚠️ Still blocked:", e.message));
        }
      });
      
      // Remove listeners after first interaction
      document.removeEventListener('click', unlockAudio);
      document.removeEventListener('touchstart', unlockAudio);
      document.removeEventListener('keydown', unlockAudio);
    };
    
    // Listen for ANY user interaction to unlock audio
    document.addEventListener('click', unlockAudio);
    document.addEventListener('touchstart', unlockAudio);
    document.addEventListener('keydown', unlockAudio);
    
    console.log("🔒 Audio unlock listeners added - click/tap/key anywhere to enable audio");

    peerConnection.ontrack = (e) => {
      console.log("🔊 Received audio track from AI");
      console.log("  Track details:", {
        kind: e.track.kind,
        id: e.track.id,
        label: e.track.label,
        enabled: e.track.enabled,
        muted: e.track.muted,
        readyState: e.track.readyState
      });
      
      // ✅ CRITICAL: Unmute the track if it's muted
      if (e.track.muted) {
        console.log("⚠️ Track is muted - attempting to unmute...");
        // Note: Track mute is controlled by sender, but we can monitor it
        e.track.onunmute = () => console.log("✅ Track unmuted!");
      }
      
      // Ensure track is enabled
      e.track.enabled = true;
      
      // Method 1: Standard audio element (should work)
      audioEl.srcObject = e.streams[0];
      
      // Method 2: AudioContext routing (force output)
      try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaStreamSource(e.streams[0]);
        source.connect(audioCtx.destination);
        console.log("🔊 AudioContext routing established");
        
        // Store for later resume if needed
        window.aiAudioContext = audioCtx;
        window.aiAudioSource = source;
      } catch (err) {
        console.error("AudioContext routing failed:", err);
      }
      
      // Try to unlock immediately if not already unlocked
      if (!audioUnlocked) {
        console.log("💡 Audio track received but not unlocked yet - click anywhere!");
      } else {
        // Already unlocked, ensure playing
        audioEl.play()
          .then(() => console.log("✅ Audio element playing"))
          .catch(e => console.log("⚠️ Audio element blocked:", e.message));
      }
    };

    // Data channel
    dataChannel = peerConnection.createDataChannel("oai-events");
    window.voiceDataChannel = dataChannel;  // ← Expose for MedGemma injection

    dataChannel.onopen = () => {
      console.log("✅ Data channel open");
      console.log("💡 MedGemma findings will now be auto-injected into voice context");
      console.log("📡 Using backend token configuration (audio + text modalities)");
      
      statusText.innerText = "👂 Listening...";
      micCircle.classList.remove('disabled');
    };

    dataChannel.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      
      // Log all messages for debugging
      console.log("📨 Data channel message:", msg.type);

      if (msg.type === "response.audio.delta") {
        micCircle.classList.add("speaking");
        statusText.innerText = "🗣 AI Speaking...";
      }

      if (msg.type === "response.audio.done") {
        micCircle.classList.remove("speaking");
        statusText.innerText = "👂 Listening...";
      }
      
      // ✅ Log when user speech is detected
      if (msg.type === "input_audio_buffer.speech_started") {
        console.log("🎤 User started speaking");
        statusText.innerText = "🎤 Listening to you...";
      }
      
      if (msg.type === "input_audio_buffer.speech_stopped") {
        console.log("🎤 User stopped speaking");
        statusText.innerText = "⏳ Processing...";
      }

      if (msg.type === "conversation.item.input_audio_transcription.completed") {
        const userText = msg.transcript || "";
        console.log("📝 User said:", userText);
        statusText.innerText = `You: "${userText}"`;

        // Clarify trigger
        if (userText.toLowerCase().includes("clarify") || 
            userText.toLowerCase().includes("what is") || 
            userText.toLowerCase().includes("explain")) {
          
          if (Date.now() - lastClarify < 4000) return;
          lastClarify = Date.now();

          fetch("/api/gi/clarify", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ question: userText })
          })
          .then(r => r.json())
          .then(data => {
            dataChannel.send(JSON.stringify({
              type: "conversation.item.create",
              item: {
                type: "message",
                role: "user",
                content: [{
                  type: "input_text",
                  text: "Based on the latest MedGemma analysis: " + data.answer
                }]
              }
            }));

            dataChannel.send(JSON.stringify({
              type: "response.create",
              response: { modalities: ["audio"] }
            }));
          })
          .catch(err => console.error("Clarify error:", err));
        }
      }
      
      // Log responses being created
      if (msg.type === "response.created") {
        console.log("🤖 AI generating response...");
      }
      
      if (msg.type === "response.done") {
        console.log("✅ AI response complete");
      }
      
      // Log any errors
      if (msg.type === "error") {
        console.error("❌ OpenAI error:", msg);
        statusText.innerText = "❌ Error: " + (msg.error?.message || "Unknown error");
      }
    };

    // Create offer with explicit audio receiving
    const offer = await peerConnection.createOffer({
      offerToReceiveAudio: true,  // ← CRITICAL: Tell OpenAI we want to receive audio
      offerToReceiveVideo: false
    });
    
    // Prefer Opus codec (what OpenAI uses)
    offer.sdp = offer.sdp.replace(/a=fmtp:111/, 'a=fmtp:111 maxaveragebitrate=128000');
    
    await peerConnection.setLocalDescription(offer);
    
    console.log("🎙️ Offer created - requesting audio stream from OpenAI");
    console.log("📋 SDP Offer:", offer.sdp.substring(0, 500) + "...");

    // Send to OpenAI with model parameter
    const sdpRes = await fetch("https://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/sdp"
      },
      body: offer.sdp
    });

    const answerSDP = await sdpRes.text();
    console.log("📋 SDP Answer from OpenAI:", answerSDP.substring(0, 500) + "...");
    
    // Check if answer includes audio
    if (answerSDP.includes('m=audio')) {
      console.log("✅ OpenAI answer includes audio media!");
    } else {
      console.error("❌ OpenAI answer does NOT include audio media!");
    }
    
    await peerConnection.setRemoteDescription({
      type: "answer",
      sdp: answerSDP
    });

    console.log("✅ Voice session connected");

  } catch (error) {
    console.error("Voice session error:", error);
    if (statusText) statusText.innerText = "❌ Voice session failed. Check console.";
    if (micCircle) micCircle.classList.add('disabled');
  }
}

/* ================================
   VIDEO UPLOAD
================================ */

function handleFileSelect(event) {
  const file = event.target.files[0];
  
  if (!file) return;
  
  // Validate file type
  const validTypes = ['video/mp4', 'video/avi', 'video/quicktime'];
  if (!validTypes.includes(file.type)) {
    alert('Please select a valid video file (MP4, AVI, MOV)');
    return;
  }
  
  // Validate file size (2GB max)
  const maxSize = 2 * 1024 * 1024 * 1024;
  if (file.size > maxSize) {
    alert('File size exceeds 2GB limit');
    return;
  }
  
  selectedFile = file;
  
  // Show file info
  document.getElementById('fileInfo').classList.add('active');
  document.getElementById('fileName').textContent = file.name;
  document.getElementById('fileSize').textContent = `Size: ${formatFileSize(file.size)}`;
  
  // Enable upload button if title and type are filled
  validateUploadForm();
}

function validateUploadForm() {
  const title = document.getElementById('videoTitle').value.trim();
  const type = document.getElementById('procedureType').value;
  const uploadBtn = document.getElementById('uploadBtn');
  
  if (selectedFile && title && type) {
    uploadBtn.disabled = false;
  } else {
    uploadBtn.disabled = true;
  }
}

// Add event listeners to form fields
document.getElementById('videoTitle').addEventListener('input', validateUploadForm);
document.getElementById('procedureType').addEventListener('change', validateUploadForm);

async function uploadVideo() {
  if (!selectedFile) {
    alert('Please select a video file');
    return;
  }
  
  const title = document.getElementById('videoTitle').value.trim();
  const procedureType = document.getElementById('procedureType').value;
  const description = document.getElementById('videoDescription').value.trim();
  
  if (!title || !procedureType) {
    alert('Please fill in all required fields');
    return;
  }
  
  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('title', title);
  formData.append('procedure_type', procedureType);
  if (description) {
    formData.append('description', description);
  }
  
  // Show progress
  const progressBar = document.getElementById('uploadProgress');
  const progressFill = document.getElementById('progressFill');
  const uploadStatus = document.getElementById('uploadStatus');
  const uploadBtn = document.getElementById('uploadBtn');
  
  progressBar.classList.add('active');
  uploadBtn.disabled = true;
  uploadStatus.innerHTML = '<span style="color: #4CAF50;">⏳ Uploading...</span>';
  
  try {
    // Simulate progress (actual progress would need server-sent events)
    let progress = 0;
    const progressInterval = setInterval(() => {
      progress += 5;
      if (progress <= 90) {
        progressFill.style.width = progress + '%';
      }
    }, 200);
    
    const response = await fetch('/api/v1/videos/upload', {
      method: 'POST',
      body: formData
    });
    
    clearInterval(progressInterval);
    
    if (!response.ok) {
      throw new Error('Upload failed');
    }
    
    const data = await response.json();
    
    progressFill.style.width = '100%';
    uploadStatus.innerHTML = `
      <span style="color: #4CAF50;">✅ Upload successful!</span><br>
      <span style="font-size: 13px; opacity: 0.7;">Processing started. Session ID: ${data.session_id.substring(0, 8)}...</span>
    `;
    
    currentSessionId = data.session_id;
    
    // Reset form after 2 seconds and switch to sessions tab
    setTimeout(() => {
      resetUploadForm();
      switchTab('sessions');
      loadSessions();
    }, 2000);
    
  } catch (error) {
    console.error('Upload error:', error);
    progressFill.style.width = '0%';
    uploadStatus.innerHTML = '<span style="color: #F44336;">❌ Upload failed. Please try again.</span>';
    uploadBtn.disabled = false;
  }
}

function resetUploadForm() {
  selectedFile = null;
  document.getElementById('videoFileInput').value = '';
  document.getElementById('videoTitle').value = '';
  document.getElementById('procedureType').value = '';
  document.getElementById('videoDescription').value = '';
  document.getElementById('fileInfo').classList.remove('active');
  document.getElementById('uploadProgress').classList.remove('active');
  document.getElementById('progressFill').style.width = '0%';
  document.getElementById('uploadStatus').innerHTML = '';
  document.getElementById('uploadBtn').disabled = true;
}

/* ================================
   SESSIONS MANAGEMENT
================================ */

async function loadSessions() {
  const grid = document.getElementById('sessionsGrid');
  grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">⏳</div><p>Loading sessions...</p></div>';
  
  try {
    const response = await fetch('/api/v1/videos/');
    const data = await response.json();
    
    if (!data.sessions || data.sessions.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📂</div>
          <p>No sessions yet</p>
          <button class="upload-button" onclick="switchTab('upload')" style="margin-top: 20px;">
            Upload Your First Video
          </button>
        </div>
      `;
      return;
    }
    
    grid.innerHTML = '';
    
    data.sessions.forEach(session => {
      const card = createSessionCard(session);
      grid.appendChild(card);
    });
    
    // Start polling for processing sessions
    startSessionPolling(data.sessions);
    
  } catch (error) {
    console.error('Error loading sessions:', error);
    grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">❌</div><p>Error loading sessions</p></div>';
  }
}

function createSessionCard(session) {
  const card = document.createElement('div');
  card.className = 'session-card';
  card.dataset.sessionId = session.session_id;
  
  const statusClass = session.processing_status === 'completed' ? 'completed' : 
                     session.processing_status === 'processing' ? 'processing' : 'pending';
  
  card.innerHTML = `
    <div class="session-header">
      <div>
        <div class="session-title">${session.title}</div>
        <div class="session-date">${formatDate(session.created_at)}</div>
      </div>
      <div class="status-badge ${statusClass}">${session.processing_status}</div>
    </div>
    
    <div style="margin: 15px 0; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 6px;">
      <div style="font-size: 13px; opacity: 0.7;">Procedure Type</div>
      <div style="font-size: 14px; margin-top: 4px;">${session.procedure_type ? formatProcedureType(session.procedure_type) : 'Not specified'}</div>
    </div>
    
    <div class="session-actions">
      ${session.processing_status === 'completed' ? `
        <button class="action-button primary" onclick="viewAnalysis('${session.session_id}')">
          📊 View Analysis
        </button>
        <button class="action-button" onclick="downloadExport('${session.session_id}')">
          💾 Download
        </button>
      ` : session.processing_status === 'processing' ? `
        <button class="action-button" disabled>
          ⏳ Processing...
        </button>
      ` : `
        <button class="action-button" disabled>
          ⏸ Pending
        </button>
      `}
    </div>
  `;
  
  return card;
}

let pollingInterval = null;

function startSessionPolling(sessions) {
  // Clear existing interval
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
  
  // Check if any sessions are processing
  const hasProcessing = sessions.some(s => s.processing_status === 'processing');
  
  if (hasProcessing) {
    pollingInterval = setInterval(() => {
      loadSessions();
    }, 60000);
  }
}

async function viewAnalysis(sessionId) {
  const modal = document.getElementById('analysisModal');
  const modalTitle = document.getElementById('modalTitle');
  const modalContent = document.getElementById('modalContent');
  
  modalTitle.textContent = 'Loading Analysis...';
  modalContent.innerHTML = '<p style="text-align: center; padding: 40px;">⏳ Loading...</p>';
  modal.classList.add('active');
  
  try {
    // Get session details and frames
    const [sessionRes, framesRes, summaryRes] = await Promise.all([
      fetch(`/api/v1/videos/${sessionId}`),
      fetch(`/api/v1/videos/${sessionId}/frames?limit=100`),
      fetch(`/api/v1/videos/${sessionId}/summary`)
    ]);
    
    const session = await sessionRes.json();
    const frames = await framesRes.json();
    const summary = await summaryRes.json();
    
    modalTitle.textContent = session.title;
    
    let html = `
      <div style="background: rgba(0,0,0,0.3); padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h3 style="margin-bottom: 15px;">📊 Statistics</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
          <div>
            <div style="opacity: 0.7; font-size: 13px;">Total Frames</div>
            <div style="font-size: 24px; font-weight: 600; color: #4CAF50;">${session.statistics.total_frames}</div>
          </div>
          <div>
            <div style="opacity: 0.7; font-size: 13px;">Analyzed</div>
            <div style="font-size: 24px; font-weight: 600; color: #4CAF50;">${session.statistics.analyzed_frames}</div>
          </div>
        </div>
      </div>
      
      <div style="background: rgba(0,0,0,0.3); padding: 20px; border-radius: 8px; margin-bottom: 20px;">
        <h3 style="margin-bottom: 15px;">📝 Summary</h3>
        <p style="line-height: 1.6; white-space: pre-wrap;">${summary.overall_summary || 'Summary not available'}</p>
      </div>
      
      <h3 style="margin-bottom: 15px;">🔬 Frame Analysis</h3>
    `;
    
    if (frames.frames && frames.frames.length > 0) {
      frames.frames.forEach(frame => {
        if (frame.analysis) {
          const riskClass = `risk-${frame.analysis.risk_level}`;
          html += `
            <div class="analysis-item">
              <div class="analysis-timestamp">
                ⏱ ${frame.timestamp}
                <span class="risk-indicator ${riskClass}">${frame.analysis.risk_level.toUpperCase()}</span>
              </div>
              <div class="analysis-finding">
                <strong>${frame.analysis.location || 'Unknown location'}:</strong><br>
                ${frame.analysis.finding || 'No finding'}
              </div>
            </div>
          `;
        }
      });
    } else {
      html += '<p style="opacity: 0.6; text-align: center; padding: 20px;">No analysis data available</p>';
    }
    
    modalContent.innerHTML = html;
    
  } catch (error) {
    console.error('Error loading analysis:', error);
    modalContent.innerHTML = '<p style="color: #F44336; text-align: center; padding: 40px;">❌ Error loading analysis</p>';
  }
}

async function downloadExport(sessionId) {
  try {
    const response = await fetch(`/api/v1/videos/${sessionId}/export`);
    const data = await response.json();
    
    // For local filesystem, we'll create a direct download link
    window.open(data.download_url, '_blank');
    
  } catch (error) {
    console.error('Error downloading export:', error);
    alert('Error downloading export. Please try again.');
  }
}

function closeModal() {
  document.getElementById('analysisModal').classList.remove('active');
}

// Close modal on outside click
document.getElementById('analysisModal').addEventListener('click', (e) => {
  if (e.target.id === 'analysisModal') {
    closeModal();
  }
});

/* ================================
   UTILITY FUNCTIONS
================================ */

function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

function formatProcedureType(type) {
  const types = {
    'upper_gi': 'Upper GI Endoscopy',
    'colonoscopy': 'Colonoscopy',
    'bronchoscopy': 'Bronchoscopy',
    'sigmoidoscopy': 'Sigmoidoscopy',
    'other': 'Other'
  };
  return types[type] || type;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (peerConnection) {
    peerConnection.close();
  }
  if (pollingInterval) {
    clearInterval(pollingInterval);
  }
});

function updateStatusIndicator(isReady) {
  const statusDot = document.getElementById('liveStatusDot');
  if (statusDot) {
    if (isReady) {
      statusDot.classList.add('ready');
    } else {
      statusDot.classList.remove('ready');
    }
  }
}