// File watch module - SSE-based live file updates

import { state } from './state.js';

// Current file watch connection
let fileWatchEventSource = null;
let currentWatchPath = null;

/**
 * Start watching a file for changes via SSE.
 *
 * @param {string} filePath - Absolute path to the file to watch
 * @param {Object} callbacks - Event handlers
 * @param {function(Object)} callbacks.onInitial - Called with initial file content
 * @param {function(Object)} callbacks.onAppend - Called when content is appended
 * @param {function(Object)} callbacks.onReplace - Called when file is replaced/rewritten
 * @param {function(string)} callbacks.onError - Called on error
 * @param {Object} options - Watch options
 * @param {boolean} options.follow - If true, detect appends and send only new bytes. If false, always send full file.
 */
export function startFileWatch(filePath, callbacks, options = {}) {
    // Stop any existing watch
    stopFileWatch();

    currentWatchPath = filePath;
    const follow = options.follow ? 'true' : 'false';
    const url = `/api/file/watch?path=${encodeURIComponent(filePath)}&follow=${follow}`;

    fileWatchEventSource = new EventSource(url);

    fileWatchEventSource.addEventListener('initial', function(e) {
        const data = JSON.parse(e.data);
        if (callbacks.onInitial) {
            callbacks.onInitial(data);
        }
    });

    fileWatchEventSource.addEventListener('append', function(e) {
        const data = JSON.parse(e.data);
        if (callbacks.onAppend) {
            callbacks.onAppend(data);
        }
    });

    fileWatchEventSource.addEventListener('replace', function(e) {
        const data = JSON.parse(e.data);
        if (callbacks.onReplace) {
            callbacks.onReplace(data);
        }
    });

    fileWatchEventSource.addEventListener('error', function(e) {
        // Check if this is an SSE error event with data
        if (e.data) {
            const data = JSON.parse(e.data);
            if (callbacks.onError) {
                callbacks.onError(data.message);
            }
        }
    });

    fileWatchEventSource.onerror = function(e) {
        // Connection error - attempt reconnect after delay
        if (fileWatchEventSource.readyState === EventSource.CLOSED) {
            console.warn('File watch connection closed, attempting reconnect...');
            // Reconnect after 1 second if we're still watching the same file
            setTimeout(function() {
                if (currentWatchPath === filePath && state.previewPaneOpen) {
                    startFileWatch(filePath, callbacks);
                }
            }, 1000);
        }
    };
}

/**
 * Stop watching the current file.
 */
export function stopFileWatch() {
    if (fileWatchEventSource) {
        fileWatchEventSource.close();
        fileWatchEventSource = null;
    }
    currentWatchPath = null;
}

/**
 * Check if currently watching a file.
 * @returns {boolean}
 */
export function isWatching() {
    return fileWatchEventSource !== null && fileWatchEventSource.readyState === EventSource.OPEN;
}

/**
 * Get the path of the currently watched file.
 * @returns {string|null}
 */
export function getWatchedPath() {
    return currentWatchPath;
}
