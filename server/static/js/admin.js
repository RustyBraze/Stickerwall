// #####################################################################################################################
// STARTUP and PRIORITY RUN / CHECK
// #####################################################################################################################

// No token, no point to load the page
const ADMIN_TOKEN = localStorage.getItem('auth_token');
if (!ADMIN_TOKEN) {
    // Redirect to login.html
    window.location.href = 'login.html';
}
// Important note: this is not a HIGH secure protection, just to keep most of the people away...

// HostURL is the key for life :D
const hostURL = window.location.origin;
// console.log(hostURL);

// For testing only
// const ADMIN_TOKEN = "supersecrettoken"; // Same as server

// #####################################################################################################################
// END STARTUP and PRIORITY RUN / CHECKS
// #####################################################################################################################




// Global Fetch function and redirects to login when token expires
async function fetchWithAuth(url, options = {}) {
    // Ensure headers exist and include the auth token
    const headers = {
        'Content-Type': 'application/json',
        'x-api-key': ADMIN_TOKEN,
        ...(options.headers || {})
    };

    try {
        const response = await fetch(url, {
            ...options,
            headers
        });

        if (response.status === 403) {
            // Clear the stored token
            localStorage.removeItem('auth_token');
            // Redirect to login page
            window.location.href = 'login.html';
            return null;
        }

        return response;
    } catch (error) {
        console.error('Network error:', error);
        throw error;
    }
}




// -----------------------------------------------------------------------------

async function fetchStickers() {
    // const response = await fetch("http://127.0.0.1:8000/api/stickers", {
    const hostEndpoint = hostURL + '/api/stickers';
    const response = await fetchWithAuth(hostEndpoint);
    // const data = await response.json();
    // return data;
    return await response.json();
}

// -----------------------------------------------------------------------------
async function deleteSticker(uuid) {
    const hostEndpoint = hostURL + `/api/stickers/${uuid}`;
    await fetchWithAuth(hostEndpoint, {
        method: 'DELETE'
    });
    location.reload();
}

// -----------------------------------------------------------------------------
function showStickerModal(sticker) {
    console.log(sticker);
    console.log('running showStickerModal');

    const modal = document.getElementById('stickerModal');
    const modalImage = document.getElementById('modalStickerImage');
    const modalUsers = document.getElementById('modalUserList');
    const modalStickerId = document.getElementById('modalStickerId');
    const modalBtnShowSticker = document.getElementById('modalBtnShowSticker');
    const modalBtnBanSticker = document.getElementById('modalBtnBanSticker');

    modalImage.src = sticker.file_path;
    modalStickerId.value = sticker.sticker_id;

    // Clear previous user list
    modalUsers.innerHTML = '';

    // Add users who sent this sticker
    sticker.users.forEach(user => {
        const userItem = document.createElement('div');
        userItem.className = 'list-group-item';
        userItem.innerHTML = `
            <div class="row align-items-center">
                <div class="col">
                    <div class="text-body">${user.telegram_user}</div>
                    <div class="text-muted">${user.telegram_id}</div>
                </div>
            </div>
        `;
        modalUsers.appendChild(userItem);
    });

    // let's configure the buttons Show/Ban
    if (sticker.banned) {
        // Disable Show/Hide btn
        modalBtnShowSticker.classList.add('disabled');
        modalBtnShowSticker.textContent = 'Show';

        modalBtnBanSticker.textContent = 'Unban';
        modalBtnBanSticker.onclick = async () => {
            await unbanSticker(sticker.sticker_id);
            await loadStickers();
            await hideStickerModal();
        }


    } else {
        // Show Show/Hide btn
        modalBtnShowSticker.classList.remove('disabled');

        modalBtnShowSticker.textContent = (sticker.visible) ? 'Hide' : 'Show';

        // Add the actions
        modalBtnShowSticker.onclick = async () => {
            if (sticker.visible) {
                await hideSticker(sticker.sticker_id);
            } else {
                await showSticker(sticker.sticker_id);
            }
            await loadStickers();
            await hideStickerModal();
        };

        modalBtnBanSticker.textContent = 'Ban';
        modalBtnBanSticker.onclick = async () => {
            const reason = prompt('Reason for banning this sticker?');
            if (reason !== null) {
                // returns NULL if the user cancels the box
                await banSticker(sticker.sticker_id, reason);
                await loadStickers();
                await hideStickerModal();
            }
        }

    }

    // Show the modal
    //<div class="modal modal-blur show" id="stickerModal" tabindex="-1" style="display: block;" aria-hidden="false" aria-modal="true">
    // modal.setAttribute('data-show', '');
    modal.classList.remove('fade');
    modal.classList.add('show');
    modal.style.display = 'block';
    modal.removeAttribute('aria-hidden');
    // modal.setAttribute('aria-hidden', 'false');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('role', 'dialog');
}





// -----------------------------------------------------------------------------
// Ban a sticker 2.0
async function banSticker(stickerUuid, reason = '') {
    const hostEndpoint = hostURL + `/api/stickers/${stickerUuid}`;
    return await fetchWithAuth(hostEndpoint, {
        method: 'POST',
        body: JSON.stringify({
            type: 'ban',
            reason: (reason === '') ? null : reason
        })
    });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Unban a sticker
async function unbanSticker(stickerUuid) {
    const hostEndpoint = hostURL + `/api/stickers/${stickerUuid}`;
    return await fetchWithAuth(hostEndpoint, {
        method: 'POST',
        body: JSON.stringify({
            type: 'unban'
        })
    });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Hide a sticker
async function hideSticker(stickerUuid) {
    const hostEndpoint = hostURL + `/api/stickers/${stickerUuid}`;
    return await fetchWithAuth(hostEndpoint, {
        method: 'POST',
        body: JSON.stringify({
            type: 'hide'
        })
    });
}
// -----------------------------------------------------------------------------

// -----------------------------------------------------------------------------
// Show a sticker
async function showSticker(stickerUuid) {
    const hostEndpoint = hostURL + `/api/stickers/${stickerUuid}`;
    return await fetchWithAuth(hostEndpoint, {
        method: 'POST',
        body: JSON.stringify({
            type: 'show'
        })
    });
}
// -----------------------------------------------------------------------------
















// -----------------------------------------------------------------------------
function hideStickerModal() {
    const modal = document.getElementById('stickerModal');

    // Restore original state
    //from this: <div class="modal modal-blur show" id="stickerModal" tabindex="-1" style="display: block;" aria-hidden="false" aria-modal="true">
    //  to this: <div class="modal modal-blur fade" id="stickerModal" tabindex="-1" style="display: none;"  aria-hidden="true">
    modal.removeAttribute('aria-modal');
    // modal.setAttribute('aria-hidden', 'true');
    modal.classList.remove('show');
    modal.classList.add('fade');
    modal.style.display = 'none';
}
// -----------------------------------------------------------------------------









// -----------------------------------------------------------------------------
async function loadStickers() {
    const stickers = await fetchStickers();
    // console.log(stickers);

    const activeContainer = document.getElementById("sticker_active");
    const inactiveContainer = document.getElementById("sticker_inactive");
    const bannedContainer = document.getElementById("sticker_banned");

    // Clear existing content
    activeContainer.innerHTML = '';
    inactiveContainer.innerHTML = '';
    bannedContainer.innerHTML = '';

    // Group stickers by sticker_id
    const stickerGroups = {};

    stickers.forEach(sticker => {
        if (!stickerGroups[sticker.sticker_uuid]) {

            stickerGroups[sticker.sticker_uuid] = {
                sticker_id: sticker.sticker_uuid,
                file_path: sticker.file_path,
                visible: sticker.visible,
                banned: sticker.banned,
                boost_factor: sticker.boost_factor,
                stats: sticker.stats,
                users: []
            };

            const usergroup = sticker.telegram;

            usergroup.forEach(sticker_telegram => {
                stickerGroups[sticker.sticker_uuid].users.push({
                    telegram_user: sticker_telegram.user,
                    telegram_id: sticker_telegram.id
                });
            });
        }
    });
    // console.log(stickerGroups);

    // Create and append sticker elements
    Object.values(stickerGroups).forEach(stickerGroup => {
        let container;

        if (stickerGroup.banned) {
            container = bannedContainer;
        } else {
            container = stickerGroup.visible ? activeContainer : inactiveContainer;
        }

        // const container = stickerGroup.visible ? activeContainer : inactiveContainer;

        const img = document.createElement('img');
        img.className = 'sticker';
        img.src = stickerGroup.file_path;
        img.alt = "Sticker";
        img.onclick = () => showStickerModal(stickerGroup);

        container.appendChild(img);
    });

    // const stickers = await fetchStickers();
    //
    // const activeContainer = document.getElementById("sticker_active");
    // const inactiveContainer = document.getElementById("sticker_inactive");
    //
    // // Clear existing content
    // activeContainer.innerHTML = '';
    // inactiveContainer.innerHTML = '';
    //
    // stickers.forEach(sticker => {
    //     const container = sticker.visible ? activeContainer : inactiveContainer;
    //
    //     const stickerDiv = document.createElement('div');
    //     stickerDiv.className = 'sticker-container';
    //
    //     const img = document.createElement('img');
    //     img.className = 'sticker';
    //     img.src = sticker.file_path;
    //     img.alt = "Sticker";
    //
    //     // const statsDiv = document.createElement('div');
    //     // statsDiv.className = 'sticker-stats';
    //     // statsDiv.innerHTML = `
    //     //     <span>Uses: ${sticker.stats.total_uses}</span>
    //     //     <span>Users: ${sticker.stats.unique_users}</span>
    //     //     <span>Boost: ${sticker.boost_factor}</span>
    //     // `;
    //
    //     stickerDiv.appendChild(img);
    //     // stickerDiv.appendChild(statsDiv);
    //
    //     if (sticker.banned) {
    //         const banLabel = document.createElement('div');
    //         banLabel.className = 'ban-label';
    //         banLabel.textContent = 'BANNED';
    //         if (sticker.reason) {
    //             banLabel.title = `Reason: ${sticker.reason}`;
    //         }
    //         stickerDiv.appendChild(banLabel);
    //     }
    //
    //     stickerDiv.onclick = () => showStickerModal(sticker);
    //     container.appendChild(stickerDiv);
    // });
}
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
async function clearAll() {
    if (confirm("Are you sure you want to clear ALL stickers?")) {
        const stickers = await fetchStickers();
        for (const id of stickers) {
            await deleteSticker(id);
        }
        location.reload();
    }
}
// -----------------------------------------------------------------------------


// -----------------------------------------------------------------------------
function showTab(tab) {
    document.getElementById('stickersTab').style.display = (tab === 'stickers') ? 'block' : 'none';
    document.getElementById('configTab').style.display = (tab === 'config') ? 'block' : 'none';
}
// -----------------------------------------------------------------------------





// #####################################################################################################################
// Event Listeners
// #####################################################################################################################
// After the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Load all the stickers
    loadStickers();

    // Close button handler
    // const closeButton = document.querySelector('#stickerModal .btn-close');
    // const closeButton = document.querySelector('.btn-close-event');
    // if (closeButton) {
    //     closeButton.addEventListener('click', hideStickerModal);
    // }
    document.querySelectorAll('.btn-close-event').forEach(btn => {
        btn.addEventListener('click', hideStickerModal);
    })


    // Click outside modal handler
    const modal = document.getElementById('stickerModal');
    modal.addEventListener('click', function(event) {
        // Check if click was on the modal backdrop (modal itself) and not its contents
        if (event.target === modal) {
            hideStickerModal();
        }
    });

    // Optional: ESC key handler
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape' && modal.classList.contains('show')) {
            hideStickerModal();
        }
    });


    // -----------------------------------------------------------------------------
    // Update the delete button handler
    // -----------------------------------------------------------------------------
    document.getElementById('deleteStickerBtn').addEventListener('click', async () => {
        const stickerId = document.getElementById('modalStickerId').value;
        if (confirm("Are you sure you want to delete this sticker?")) {
            await deleteSticker(stickerId);
            const modal = document.getElementById('stickerModal');
            modal.removeAttribute('data-show');
            await loadStickers();
        }
    });

});
// -----------------------------------------------------------------------------


// #####################################################################################################################
// END Event Listeners
// #####################################################################################################################










