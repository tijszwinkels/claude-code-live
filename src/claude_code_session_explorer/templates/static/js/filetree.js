
import { dom, state } from './state.js';
import { openPreviewPane, closePreviewPane } from './preview.js';

export function initFileTree() {
    // Toggle button in status bar
    if (dom.rightSidebarToggle) {
        dom.rightSidebarToggle.addEventListener('click', toggleRightSidebar);
    }

    // View switcher buttons
    if (dom.showPreviewBtn) {
        dom.showPreviewBtn.addEventListener('click', () => switchView('preview'));
    }
    if (dom.showTreeBtn) {
        dom.showTreeBtn.addEventListener('click', () => switchView('tree'));
    }
}

export async function loadFileTree(sessionId) {
    if (!sessionId) return;

    if (!dom.fileTreeContent) return;
    
    // Check if we already have the tree for this session? 
    // Maybe just reload it to be safe (it's fast)
    
    dom.fileTreeContent.innerHTML = '<div class="preview-status visible loading">Loading tree...</div>';
    
    try {
        const response = await fetch(`/sessions/${sessionId}/tree`);
        const data = await response.json();
        
        if (data.error || !data.tree) {
             dom.fileTreeContent.innerHTML = `<div class="preview-status visible warning">${data.error || 'No tree data'}</div>`;
             return;
        }
        
        renderTree(data.tree);
        
        // Show the toggle button since we have a tree (if hidden by default)
        // dom.rightSidebarToggle.style.display = 'block'; 
        
    } catch (err) {
        if (dom.fileTreeContent) {
            dom.fileTreeContent.innerHTML = `<div class="preview-status visible error">Error loading tree: ${err.message}</div>`;
        }
    }
}

function renderTree(treeData) {
    dom.fileTreeContent.innerHTML = '';
    const rootUl = document.createElement('ul');
    rootUl.className = 'tree-root';
    
    // The root itself (project dir) - usually we skip rendering the root node itself 
    // and just render children, or render root as open details.
    // Let's render root children directly to save horizontal space.
    if (treeData.children) {
        const sortedChildren = sortChildren(treeData.children);
        sortedChildren.forEach(child => {
            rootUl.appendChild(createTreeItem(child));
        });
    }
    
    dom.fileTreeContent.appendChild(rootUl);
}

function sortChildren(children) {
    return children.sort((a, b) => {
        if (a.type === b.type) return a.name.localeCompare(b.name);
        return a.type === 'directory' ? -1 : 1;
    });
}

function createTreeItem(item) {
    const li = document.createElement('li');
    li.className = 'tree-item';
    
    if (item.type === 'directory') {
        const details = document.createElement('details');
        const summary = document.createElement('summary');
        summary.className = 'tree-summary';
        summary.innerHTML = `<span class="tree-icon tree-icon-folder"></span> ${item.name}`;
        
        details.appendChild(summary);
        
        if (item.children && item.children.length > 0) {
            const ul = document.createElement('ul');
            ul.className = 'tree-children';
            
            const sortedChildren = sortChildren(item.children);
            
            sortedChildren.forEach(child => {
                ul.appendChild(createTreeItem(child));
            });
            details.appendChild(ul);
        }
        
        li.appendChild(details);
    } else {
        const div = document.createElement('div');
        div.className = 'tree-summary';
        div.innerHTML = `<span class="tree-icon tree-icon-file"></span> ${item.name}`;
        div.dataset.path = item.path;
        
        div.addEventListener('click', (e) => {
            // Highlight selection
            document.querySelectorAll('.tree-summary.selected').forEach(el => el.classList.remove('selected'));
            div.classList.add('selected');
            
            // Open preview
            openPreviewPane(item.path);
            
            // Switch to preview view
            switchView('preview');
        });
        
        li.appendChild(div);
    }
    
    return li;
}

function toggleRightSidebar() {
    if (state.previewPaneOpen) {
        // If open, close it
        closePreviewPane(false);
    } else {
        // Open tree view by default
        openRightPane('tree');
    }
}

export function openRightPane(view = 'tree') {
    dom.previewPane.classList.add('open');
    dom.mainContent.classList.add('preview-open');
    dom.inputBar.classList.add('preview-open');
    dom.floatingControls.classList.add('preview-open');
    state.previewPaneOpen = true;
    
    switchView(view);
}

export function switchView(view) {
    const isTree = view === 'tree';
    
    if (dom.viewSwitcher) {
        dom.viewSwitcher.style.display = 'flex';
        dom.showTreeBtn.classList.toggle('active', isTree);
        dom.showPreviewBtn.classList.toggle('active', !isTree);
    }
    
    if (dom.fileTreeContent) {
        dom.fileTreeContent.style.display = isTree ? 'block' : 'none';
    }
    
    if (dom.previewContent) {
        dom.previewContent.style.display = !isTree ? 'block' : 'none';
    }
    
    // Toggle other preview elements
    if (dom.previewViewToggle) {
        const showToggle = !isTree && state.previewFileData && state.previewFileData.rendered_html;
        dom.previewViewToggle.style.display = showToggle ? 'flex' : 'none';
    }
    
    if (dom.previewPath) {
        dom.previewPath.style.display = !isTree ? 'block' : 'none';
    }
    
    if (dom.previewCopyBtn) {
        dom.previewCopyBtn.style.display = !isTree ? 'block' : 'none';
    }
    
    // Update title
    if (isTree) {
        dom.previewFilename.textContent = 'File Tree';
    } else if (state.previewFilePath) {
        dom.previewFilename.textContent = state.previewFilePath.split('/').pop();
    }
}
