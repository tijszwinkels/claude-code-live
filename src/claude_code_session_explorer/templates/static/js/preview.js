
import { dom, state } from './state.js';
import { isMobile, copyToClipboard } from './utils.js';
import { openRightPane, syncTreeToFile, loadFileTree } from './filetree.js';
import { showFlash } from './ui.js';

// Initialize preview pane width
export function initPreviewPane() {
    document.documentElement.style.setProperty('--preview-pane-width', state.previewPaneWidth + 'px');

    // Close button
    dom.previewCloseBtn.addEventListener('click', closePreviewPane);

    // Copy path button
    if (dom.previewCopyBtn) {
        dom.previewCopyBtn.addEventListener('click', function() {
            if (state.previewFilePath) {
                copyToClipboard(state.previewFilePath, null);
                const originalText = dom.previewCopyBtn.textContent;
                dom.previewCopyBtn.textContent = 'Copied!';
                setTimeout(() => dom.previewCopyBtn.textContent = originalText, 1500);
            }
        });
    }

    // View toggle for markdown files
    if (dom.previewViewCheckbox) {
        dom.previewViewCheckbox.addEventListener('change', function() {
            updateViewToggleLabel();
            if (state.previewFileData) {
                renderPreviewContent(state.previewFileData, dom.previewViewCheckbox.checked);
            }
        });
    }

    // Escape key to close preview pane
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && state.previewPaneOpen) {
            closePreviewPane();
        }
    });

    // Click on file paths to open preview, or URLs to copy them (except copy button)
    // This handles both explicit file-tool-fullpath elements and any text that looks like a file path or URL
    document.addEventListener('click', async function(e) {
        // Skip if clicking the copy button
        if (e.target.closest('.copy-btn')) return;

        // Skip if clicking links (let them navigate normally)
        if (e.target.closest('a')) return;

        // Skip if user has selected text (they're trying to copy)
        const selection = window.getSelection();
        if (selection && selection.toString().length > 0) return;

        // First, check for explicit file-tool-fullpath elements (highest priority)
        const fullpath = e.target.closest('.file-tool-fullpath[data-copy-path]');
        if (fullpath) {
            e.preventDefault();
            e.stopPropagation();
            const path = fullpath.dataset.copyPath;
            openPreviewPane(path);
            return;
        }

        // Try to detect URL from clicked text
        const url = extractUrlFromClick(e);
        if (url) {
            copyToClipboard(url, null);
            showFlash('URL copied to clipboard', 'success', 2000);
            return;
        }

        // Otherwise, try to detect file path from clicked text
        const filePath = extractFilePathFromClick(e);
        if (filePath) {
            // Check path type and handle accordingly (silently fail if not found)
            const pathType = await getPathType(filePath);
            if (pathType === 'file') {
                openPreviewPane(filePath);
            } else if (pathType === 'directory' && state.activeSessionId) {
                // Navigate file tree to this directory
                openRightPane();
                loadFileTree(state.activeSessionId, filePath);
            }
        }
    });

    // Preview pane resize handle
    dom.previewResizeHandle.addEventListener('mousedown', function(e) {
        if (isMobile()) return;
        state.isPreviewResizing = true;
        state.previewStartX = e.clientX;
        state.previewStartWidth = state.previewPaneWidth;
        dom.previewResizeHandle.classList.add('dragging');
        document.body.style.cursor = 'ew-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', function(e) {
        if (!state.isPreviewResizing) return;

        const delta = state.previewStartX - e.clientX;  // Note: reversed because resizing from left edge
        let newWidth = state.previewStartWidth + delta;

        // Clamp width: min 500px (split view), max 90% of viewport
        const maxWidth = window.innerWidth * 0.9;
        newWidth = Math.max(500, Math.min(maxWidth, newWidth));

        state.previewPaneWidth = newWidth;
        document.documentElement.style.setProperty('--preview-pane-width', newWidth + 'px');
    });

    document.addEventListener('mouseup', function() {
        if (state.isPreviewResizing) {
            state.isPreviewResizing = false;
            dom.previewResizeHandle.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            localStorage.setItem('previewPaneWidth', state.previewPaneWidth);
        }
    });
}

export async function openPreviewPane(filePath) {
    state.previewFilePath = filePath;
    state.previewFileData = null;
    const filename = filePath.split('/').pop();

    // Track this preview for the current session
    if (state.activeSessionId) {
        state.sessionPreviewPaths.set(state.activeSessionId, filePath);
    }

    if (dom.previewFilename) dom.previewFilename.textContent = filename;
    if (dom.previewPath) dom.previewPath.textContent = filePath;
    if (dom.previewContent) dom.previewContent.innerHTML = '';
    if (dom.previewViewToggle) dom.previewViewToggle.style.display = 'none';  // Hide toggle until we know if it's markdown
    if (dom.previewCopyBtn) dom.previewCopyBtn.style.display = 'block';
    
    showPreviewStatus('loading', 'Loading...');

    // Open the pane (ensures parent classes are set)
    openRightPane();
    
    // Sync tree to this file
    syncTreeToFile(filePath);

    try {
        const response = await fetch(`/api/file?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();

        if (!response.ok) {
            showPreviewStatus('error', data.detail || 'Failed to load file');
            return;
        }

        // Store data for view toggle
        state.previewFileData = data;

        // Show toggle for markdown files
        if (data.rendered_html && dom.previewViewToggle) {
            dom.previewViewToggle.style.display = '';
            dom.previewViewCheckbox.checked = true;
            updateViewToggleLabel();
        }

        // Render content with syntax highlighting
        renderPreviewContent(data, dom.previewViewCheckbox ? dom.previewViewCheckbox.checked : true);

        if (data.truncated) {
            showPreviewStatus('warning', 'File truncated (showing first 1MB)');
        } else {
            hidePreviewStatus();
        }
    } catch (err) {
        showPreviewStatus('error', 'Failed to load file: ' + err.message);
    }
}

export function closePreviewPane(clearSessionAssociation = true) {
    dom.previewPane.classList.remove('open');
    dom.mainContent.classList.remove('preview-open');
    dom.inputBar.classList.remove('preview-open');
    dom.floatingControls.classList.remove('preview-open');
    state.previewPaneOpen = false;
    state.previewFilePath = null;
    state.previewFileData = null;

    // Clear session association if requested (not when switching sessions)
    if (clearSessionAssociation && state.activeSessionId) {
        state.sessionPreviewPaths.delete(state.activeSessionId);
    }
}

function renderPreviewContent(data, showRendered = true) {
    if (!dom.previewContent) return;
    
    dom.previewContent.innerHTML = '';

    // If we have pre-rendered HTML (markdown) and showRendered is true, display that
    if (data.rendered_html && showRendered) {
        const wrapper = document.createElement('div');
        wrapper.className = 'markdown-preview';
        wrapper.innerHTML = data.rendered_html;
        dom.previewContent.appendChild(wrapper);

        // Apply highlight.js to any code blocks in the markdown
        if (window.hljs) {
            wrapper.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
        return;
    }

    // Otherwise render as code with syntax highlighting
    const pre = document.createElement('pre');
    const code = document.createElement('code');

    // Set language class if detected
    if (data.language) {
        code.className = 'language-' + data.language;
    }

    code.textContent = data.content;
    pre.appendChild(code);
    dom.previewContent.appendChild(pre);

    // Apply highlight.js if available
    if (window.hljs) {
        hljs.highlightElement(code);
    }
}

function showPreviewStatus(type, message) {
    if (!dom.previewStatus) return;
    dom.previewStatus.className = 'preview-status visible ' + type;
    dom.previewStatus.textContent = message;
}

function hidePreviewStatus() {
    if (!dom.previewStatus) return;
    dom.previewStatus.className = 'preview-status';
}

function updateViewToggleLabel() {
    if (!dom.previewViewToggle) return;
    const label = dom.previewViewToggle.querySelector('.toggle-label');
    if (label) {
        label.textContent = dom.previewViewCheckbox.checked ? 'Rendered' : 'Source';
    }
}

/**
 * Extract a URL from clicked text.
 * Tries to find http:// or https:// URL in or around the clicked element.
 * Returns null if no valid URL is found.
 */
function extractUrlFromClick(event) {
    const target = event.target;

    // Get the text content of the clicked element or its innermost text node
    let text = '';

    if (target.nodeType === Node.ELEMENT_NODE) {
        // Try to get the specific text at the click position using Range
        const clickedText = getUrlTextAtPoint(event.clientX, event.clientY);
        if (clickedText) {
            text = clickedText;
        } else {
            // Fall back to element's text content
            text = target.textContent || '';
        }
    }

    if (!text) return null;

    // Try to extract a URL from the text
    return findUrlInText(text);
}

/**
 * Get the URL text content at a specific point.
 * Similar to getTextAtPoint but includes URL-valid characters like : and ?
 */
function getUrlTextAtPoint(x, y) {
    let textNode;
    let offset;

    // Try caretPositionFromPoint (Firefox) or caretRangeFromPoint (Chrome/Safari)
    if (document.caretPositionFromPoint) {
        const pos = document.caretPositionFromPoint(x, y);
        if (pos && pos.offsetNode) {
            textNode = pos.offsetNode;
            offset = pos.offset;
        }
    } else if (document.caretRangeFromPoint) {
        const range = document.caretRangeFromPoint(x, y);
        if (range) {
            textNode = range.startContainer;
            offset = range.startOffset;
        }
    }

    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) {
        return null;
    }

    const fullText = textNode.textContent || '';

    // URL characters - include everything valid in URLs
    // RFC 3986 unreserved: A-Z a-z 0-9 - . _ ~
    // RFC 3986 reserved: : / ? # [ ] @ ! $ & ' ( ) * + , ; =
    // Also include % for percent-encoding
    const urlChars = /[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]/;

    let start = offset;
    let end = offset;

    // Expand left
    while (start > 0 && urlChars.test(fullText[start - 1])) {
        start--;
    }

    // Expand right
    while (end < fullText.length && urlChars.test(fullText[end])) {
        end++;
    }

    const word = fullText.substring(start, end);
    return word.length > 0 ? word : null;
}

/**
 * Find a URL pattern in text.
 * Returns the URL if found, null otherwise.
 */
function findUrlInText(text) {
    // Look for http:// or https:// URLs
    const urlPattern = /https?:\/\/[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+/i;
    const match = text.match(urlPattern);

    if (match) {
        // Clean up trailing punctuation that's unlikely to be part of the URL
        let url = match[0];
        // Remove trailing punctuation like ), ], ., ,, ;, :, ! if they aren't balanced
        url = url.replace(/[)\].,;:!]+$/, '');
        // But restore ) if there's a matching ( in the URL (common in Wikipedia URLs)
        const openParens = (url.match(/\(/g) || []).length;
        const closeParens = (url.match(/\)/g) || []).length;
        if (openParens > closeParens && match[0].charAt(url.length) === ')') {
            url += ')';
        }
        return url;
    }

    return null;
}

/**
 * Extract a file path from clicked text.
 * Tries to find a file path pattern in or around the clicked element.
 * Returns null if no valid file path is found.
 */
function extractFilePathFromClick(event) {
    const target = event.target;

    // Get the text content of the clicked element or its innermost text node
    let text = '';

    // If we clicked directly on a text node's parent, get that text
    if (target.nodeType === Node.ELEMENT_NODE) {
        // Try to get the specific text at the click position using Range
        const clickedText = getTextAtPoint(event.clientX, event.clientY);
        if (clickedText) {
            text = clickedText;
        } else {
            // Fall back to element's text content
            text = target.textContent || '';
        }
    }

    if (!text) return null;

    // Try to extract a file path from the text
    return findFilePathInText(text);
}

/**
 * Get the text content at a specific point using document.caretPositionFromPoint
 * or document.caretRangeFromPoint for browser compatibility.
 */
function getTextAtPoint(x, y) {
    let range;
    let textNode;
    let offset;

    // Try caretPositionFromPoint (Firefox) or caretRangeFromPoint (Chrome/Safari)
    if (document.caretPositionFromPoint) {
        const pos = document.caretPositionFromPoint(x, y);
        if (pos && pos.offsetNode) {
            textNode = pos.offsetNode;
            offset = pos.offset;
        }
    } else if (document.caretRangeFromPoint) {
        range = document.caretRangeFromPoint(x, y);
        if (range) {
            textNode = range.startContainer;
            offset = range.startOffset;
        }
    }

    if (!textNode || textNode.nodeType !== Node.TEXT_NODE) {
        return null;
    }

    const fullText = textNode.textContent || '';

    // Find word boundaries around the click position, expanding to capture full file path
    // Include characters common in file paths: letters, numbers, /, ., -, _, ~
    let start = offset;
    let end = offset;

    // Path characters (don't include : since we want to stop before line numbers)
    const pathChars = /[a-zA-Z0-9\/._\-~]/;

    // Expand left
    while (start > 0 && pathChars.test(fullText[start - 1])) {
        start--;
    }

    // Expand right
    while (end < fullText.length && pathChars.test(fullText[end])) {
        end++;
    }

    const word = fullText.substring(start, end);
    return word.length > 0 ? word : null;
}

/**
 * Find a file path pattern in text.
 * Returns the path if found, null otherwise.
 */
function findFilePathInText(text) {
    // Skip if text starts with http:// or https:// - it's a URL
    if (/^https?:\/\//i.test(text)) {
        return null;
    }

    // Common file path patterns:
    // 1. Absolute path: /home/user/file.txt or /var/log/file.log
    // 2. Home-relative: ~/file.txt or ~/.config/file
    // 3. Relative with directories: src/components/file.tsx, ./file.txt, ../file.txt

    // Pattern explanation:
    // - Starts with /, ~/, ./, or ../
    // - Or looks like a relative path with at least one directory separator
    // - Contains valid path characters
    // - Has some minimum length to avoid false positives

    // First, try to match patterns that start with explicit path indicators
    const explicitPathPattern = /^(\/|~\/|\.\/)[\w.\-\/]+/;
    const explicitMatch = text.match(explicitPathPattern);
    if (explicitMatch) {
        return cleanFilePath(explicitMatch[0]);
    }

    // Try to match relative paths with directory structure (must have at least one /)
    // This catches things like: src/file.ts, components/Button.tsx
    const relativePathPattern = /^[\w.\-]+\/[\w.\-\/]+/;
    const relativeMatch = text.match(relativePathPattern);
    if (relativeMatch) {
        // Only return if it looks like a real file path (has a file extension or ends reasonably)
        const path = relativeMatch[0];
        if (looksLikeFilePath(path)) {
            return cleanFilePath(path);
        }
    }

    return null;
}

/**
 * Clean up a file path - remove trailing punctuation, etc.
 */
function cleanFilePath(path) {
    // Remove trailing punctuation that might have been captured
    return path.replace(/[,;:!?'")\]}>]+$/, '');
}

/**
 * Check if a string looks like a real file path.
 * Helps avoid false positives on random text.
 */
function looksLikeFilePath(text) {
    // Has a file extension
    if (/\.\w{1,10}$/.test(text)) {
        return true;
    }

    // Is a known config/dotfile pattern
    if (/\/\.\w+/.test(text)) {
        return true;
    }

    // Ends with a directory-like name (all lowercase or common patterns)
    if (/\/[a-z_\-]+$/.test(text)) {
        return true;
    }

    return false;
}

/**
 * Get the type of a path on the server.
 * Returns "file", "directory", or null if not found.
 * Never throws - returns null on any error.
 */
async function getPathType(path) {
    try {
        const response = await fetch(`/api/path/type?path=${encodeURIComponent(path)}`);
        if (!response.ok) return null;
        const data = await response.json();
        return data.type;  // "file" or "directory"
    } catch {
        return null;
    }
}
