// Library Logic
document.addEventListener('DOMContentLoaded', () => {
    const taskId = new URLSearchParams(window.location.search).get('task');
    if (taskId) {
        const list = document.getElementById('book-list');
        list.innerHTML = '<p id="progress-text">Resuming upload...</p><p id="progress-detail"></p>';
        pollTask(taskId);
        return;
    }
    loadLibrary();
});

const fileInput = document.getElementById('file-upload');
fileInput.addEventListener('change', uploadBook);

function loadLibrary() {
    fetch('/books')
        .then(res => res.json())
        .then(books => {
            const list = document.getElementById('book-list');
            list.innerHTML = '';
            if (!Array.isArray(books)) {
                list.innerHTML = 'No books found.';
                return;
            }
            books.forEach(book => {
                const card = document.createElement('div');
                card.className = 'book-card';
                let posText = `Pos: ${book.current_pos} / ${book.total_sequences}`;
                if (book.chapter_title) {
                    posText += `<br><span style="font-size:0.9em; color:#888;">${book.chapter_title}</span>`;
                }

                card.innerHTML = `
                    <h3>${book.title}</h3>
                    <p>${book.author}</p>
                    <p style="margin-top:10px; font-weight:bold; color:#2c3e50;">
                        ${posText}
                    </p>
                `;

                const actions = document.createElement('div');
                actions.className = 'book-actions';
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'delete-btn';
                deleteBtn.type = 'button';
                deleteBtn.textContent = 'Delete';
                deleteBtn.addEventListener('click', (event) => {
                    event.stopPropagation();
                    confirmDelete(book, card);
                });
                actions.appendChild(deleteBtn);
                card.appendChild(actions);

                card.onclick = () => openReader(book.hash, book.title);
                list.appendChild(card);
            });
        })
        .catch(err => {
            console.error("Load Library Error:", err);
            document.getElementById('book-list').innerHTML = "Error loading library.";
        });
}

function uploadBook(e) {
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);

    const list = document.getElementById('book-list');
    list.innerHTML = '<p id="progress-text">Uploading...</p><p id="progress-detail"></p>';
    document.querySelectorAll('.progress-container, #progress-bar').forEach(el => el.remove());

    fetch('/upload', { method: 'POST', body: formData })
        .then(res => res.json())
        .then(data => {
            const taskId = data.task_id;
            window.history.replaceState(null, '', `/?task=${encodeURIComponent(taskId)}`);
            pollTask(taskId);
        })
        .catch(err => {
            console.error(err);
            list.innerHTML = 'Error starting upload.';
        });
}

function confirmDelete(book, card) {
    const confirmed = window.confirm(`Delete "${book.title}"? This cannot be undone.`);
    if (!confirmed) {
        return;
    }

    fetch(`/books/${book.hash}`, { method: 'DELETE' })
        .then(res => {
            if (!res.ok) {
                return res.json().then(payload => {
                    throw new Error(payload.detail || 'Delete failed.');
                });
            }
            return res.json();
        })
        .then(() => {
            card.remove();
            const list = document.getElementById('book-list');
            if (!list.children.length) {
                list.innerHTML = 'No books found.';
            }
        })
        .catch(err => {
            console.error("Delete Error:", err);
            alert(err.message);
        });
}

function pollTask(taskId) {
    const interval = setInterval(() => {
        fetch(`/tasks/${taskId}`)
            .then(res => {
                if (!res.ok) {
                    const err = new Error(`Task fetch failed (${res.status})`);
                    err.status = res.status;
                    throw err;
                }
                return res.json();
            })
            .then(task => {
                const text = document.getElementById('progress-text');
                const detail = document.getElementById('progress-detail');
                document.querySelectorAll('.progress-container, #progress-bar').forEach(el => el.remove());

                if (text) text.innerText = task.message;
                if (detail) detail.innerText = task.detail || '';

                if (task.status === 'completed') {
                    clearInterval(interval);
                    loadLibrary();
                } else if (task.status === 'error') {
                    clearInterval(interval);
                    if (text) text.innerText = "Error: " + task.error;
                }
            })
            .catch(err => {
                clearInterval(interval);
                const text = document.getElementById('progress-text');
                const detail = document.getElementById('progress-detail');
                if (text) {
                    if (err.status === 404) {
                        text.innerText = "Task disappeared. Refreshing library...";
                    } else {
                        text.innerText = "Error checking task status.";
                    }
                }
                if (detail) detail.innerText = '';
                loadLibrary();
            });
    }, 1000);
}

function openReader(hash, title) {
    currentBookHash = hash;
    document.getElementById('library-view').style.display = 'none';
    const readerView = document.getElementById('reader-view');
    readerView.style.display = 'flex';
    document.getElementById('book-title').innerText = title;

    // Fetch latest status
    fetch(`/books/${hash}`)
        .then(res => res.json())
        .then(details => {
            const status = document.getElementById('status');
            let statusText = `Seq: ${details.current_pos}`;
            if (details.chapter_title) {
                statusText += ` | ${details.chapter_title}`;
            }
            status.innerText = statusText;

            // Restore Position if available
            if (details.last_cfi && book && rendition) {
                console.log("Restoring position to CFI:", details.last_cfi);
                rendition.display(details.last_cfi);
            }
        });

    const url = "/files/" + hash + ".epub";
    console.log("Loading book from:", url);

    // Load from server
    book = ePub(url);

    book.opened.then(() => {
        console.log("Book opened successfully");
    }).catch(err => {
        console.error("Error opening book:", err);
        status.innerText = "Load Error";
    });

    rendition = book.renderTo("viewer", {
        width: "100%",
        height: "100%",
        flow: "paginated"
    });

    rendition.display().catch(err => {
        console.error("Rendition display error:", err);
    });

    setupReaderEvents();
}

document.getElementById('back-btn').addEventListener('click', () => {
    document.getElementById('reader-view').style.display = 'none';
    document.getElementById('library-view').style.display = 'block';
    if (book) book.destroy();
    loadLibrary(); // Refresh library view
});

// ...

function setupReaderEvents() {
    // Navigation
    const prevBtn = document.getElementById('prev');
    const nextBtn = document.getElementById('next');
    
    // Clear old listeners by cloning (simple hack) or just re-assigning onclick
    // Since we destroy the book on back, we should be safe re-assigning onclick
    prevBtn.onclick = () => {
        console.log("Prev clicked");
        if (rendition) rendition.prev();
    };
    nextBtn.onclick = () => {
        console.log("Next clicked");
        if (rendition) rendition.next();
    };

    document.onkeyup = (e) => {
        if (e.keyCode == 37) {
            console.log("Left Arrow");
            if (rendition) rendition.prev();
        }
        if (e.keyCode == 39) {
            console.log("Right Arrow");
            if (rendition) rendition.next();
        }
    };

    // Selection / Sync
    rendition.on('selected', (cfiRange, contents) => {
        console.log("Selection Event Fired. CFI:", cfiRange);
        
        book.getRange(cfiRange).then(range => {
            let text = range.toString().replace(/[\n\r\s]+/g, ' ').trim();
            console.log("Selected Text:", text);
            
            if (text.length > 5) {
                syncPosition(text, cfiRange, contents);
            }
        });
    });
}

function syncPosition(text, cfi, contents) {
    const status = document.getElementById('status');
    status.innerText = "Syncing...";
    
    fetch('/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            book_hash: currentBookHash, 
            text: text,
            cfi: cfi // Send CFI
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'synced') {
            let statusText = `Seq: ${data.seq_id}`;
            if (data.chapter_title) {
                statusText += ` | ${data.chapter_title}`;
            }
            status.innerText = "Saved: " + statusText;
            
            if (contents && contents.window) {
                contents.window.getSelection().removeAllRanges();
            }
        } else {
            console.error("Sync Failed Response:", data);
            status.innerText = "Sync failed";
        }
    })
    .catch(err => {
        console.error("Sync Error:", err);
        status.innerText = "Error";
    });
}
