// Preview pane module - file preview functionality

import { dom, state } from './state.js';
import { isMobile, copyToClipboard } from './utils.js';
import { switchView } from './filetree.js';

// Initialize preview pane width
export function initPreviewPane() {
    document.documentElement.style.setProperty('--preview-pane-width', state.previewPaneWidth + 'px');

    // Close button
    dom.previewCloseBtn.addEventListener('click', closePreviewPane);

    // Copy path button
    dom.previewCopyBtn.addEventListener('click', function() {
        if (state.previewFilePath) {
            copyToClipboard(state.previewFilePath, null);
            const originalText = dom.previewCopyBtn.textContent;
            dom.previewCopyBtn.textContent = 'Copied!';
            setTimeout(() => dom.previewCopyBtn.textContent = originalText, 1500);
        }
    });

    // View toggle for markdown files
    dom.previewViewCheckbox.addEventListener('change', function() {
        updateViewToggleLabel();
        if (state.previewFileData) {
            renderPreviewContent(state.previewFileData, dom.previewViewCheckbox.checked);
        }
    });

    // Escape key to close preview pane
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && state.previewPaneOpen) {
            closePreviewPane();
        }
    });

    // Click on file paths to open preview (except copy button)
    document.addEventListener('click', function(e) {
        // Skip if clicking the copy button
        if (e.target.closest('.copy-btn')) return;

        const fullpath = e.target.closest('.file-tool-fullpath[data-copy-path]');
        if (!fullpath) return;

        e.preventDefault();
        e.stopPropagation();
        const path = fullpath.dataset.copyPath;
        openPreviewPane(path);
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

        // Clamp width: min 300px, max 60% of viewport
        const maxWidth = window.innerWidth * 0.6;
        newWidth = Math.max(300, Math.min(maxWidth, newWidth));

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

    dom.previewFilename.textContent = filename;
    dom.previewPath.textContent = filePath;
    dom.previewContent.innerHTML = '';
    dom.previewViewToggle.style.display = 'none';  // Hide toggle until we know if it's markdown
    showPreviewStatus('loading', 'Loading...');

    // Open the pane
    dom.previewPane.classList.add('open');
    dom.mainContent.classList.add('preview-open');
    dom.inputBar.classList.add('preview-open');
    dom.floatingControls.classList.add('preview-open');
    state.previewPaneOpen = true;

    // Ensure we are in preview mode (not tree mode)
    if (typeof switchView === 'function') {
        switchView('preview');
    }

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
        if (data.rendered_html) {
            dom.previewViewToggle.style.display = '';
            dom.previewViewCheckbox.checked = true;
            updateViewToggleLabel();
        }

        // Render content with syntax highlighting
        renderPreviewContent(data, dom.previewViewCheckbox.checked);

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
    dom.previewStatus.className = 'preview-status visible ' + type;
    dom.previewStatus.textContent = message;
}

function hidePreviewStatus() {
    dom.previewStatus.className = 'preview-status';
}

function updateViewToggleLabel() {
    const label = dom.previewViewToggle.querySelector('.toggle-label');
    label.textContent = dom.previewViewCheckbox.checked ? 'Rendered' : 'Source';
}
